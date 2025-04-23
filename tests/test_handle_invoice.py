"""
Тесты для обработчика фотографий накладных.
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock

from telegram import Update, Message, Chat, User, PhotoSize, File, CallbackQuery
from telegram.ext import ContextTypes

from config import CONFIRMATION, WAIT_PHOTO
from handlers.invoice_handlers import handle_invoice, handle_invoice_callback
from services.ocr_service import ParsedInvoice


# Фикстуры для тестирования
@pytest.fixture
def mock_context():
    """Создаёт мок контекста бота."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}
    return context


@pytest.fixture
def mock_photo_update():
    """Создаёт мок объекта Update с фотографией."""
    photo_size = MagicMock(spec=PhotoSize)
    photo_size.file_id = "test_file_id"
    photo_size.file_unique_id = "test_unique_id"
    
    photo_file = AsyncMock(spec=File)
    photo_file.file_id = "test_file_id"
    photo_file.download_to_drive = AsyncMock()
    photo_size.get_file = AsyncMock(return_value=photo_file)
    
    chat = MagicMock(spec=Chat)
    chat.id = 12345
    
    user = MagicMock(spec=User)
    user.id = 67890
    
    message = MagicMock(spec=Message)
    message.message_id = 1
    message.chat = chat
    message.from_user = user
    message.photo = [photo_size]
    message.reply_text = AsyncMock()
    
    update = MagicMock(spec=Update)
    update.message = message
    update.effective_chat = chat
    update.callback_query = None
    
    return update


@pytest.fixture
def mock_callback_update(mock_context):
    """Создаёт мок объекта Update с callback query."""
    chat = MagicMock(spec=Chat)
    chat.id = 12345
    
    user = MagicMock(spec=User)
    user.id = 67890
    
    message = MagicMock(spec=Message)
    message.message_id = 1
    message.chat = chat
    
    query = MagicMock(spec=CallbackQuery)
    query.message = message
    query.from_user = user
    query.data = f"confirm_invoice:test_invoice_id"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    
    update = MagicMock(spec=Update)
    update.message = None
    update.effective_chat = chat
    update.callback_query = query
    
    # Добавляем данные накладной в контекст
    mock_context.user_data = {
        "invoice": {
            "supplier": "Test Supplier",
            "lines": [
                {"name": "Item 1", "qty": 2, "unit": "кг", "price": 100},
                {"name": "Item 2", "qty": 1, "unit": "шт", "price": 200},
            ],
            "total": 400
        },
        "invoice_id": "test_invoice_id"
    }
    
    return update


@pytest.mark.asyncio
async def test_handle_invoice_photo(mocker, mock_photo_update, mock_context):
    """Тест обработки фотографии накладной."""
    # Подготавливаем моки
    mock_extract = mocker.patch(
        "handlers.invoice_handlers.extract",
        new=AsyncMock()
    )
    
    # Подготавливаем тестовые данные для результата OCR
    invoice_data = ParsedInvoice(
        supplier="Test Supplier",
        items=[
            {"name": "Item 1", "qty": 2, "unit": "кг", "price": 100},
            {"name": "Item 2", "qty": 1, "unit": "шт", "price": 200},
        ],
        total=400
    )
    mock_extract.return_value = invoice_data
    
    # Мокаем функции обработки данных
    mock_match = mocker.patch(
        "handlers.invoice_handlers.match_invoice_items",
        new=AsyncMock(return_value={
            "supplier": "Test Supplier",
            "lines": [
                {"name": "Item 1", "qty": 2, "unit": "кг", "price": 100, "product_id": "123"},
                {"name": "Item 2", "qty": 1, "unit": "шт", "price": 200, "product_id": "456"},
            ],
            "total": 400
        })
    )
    
    mock_conversions = mocker.patch(
        "handlers.invoice_handlers.apply_unit_conversions",
        return_value=[]
    )
    
    # Запускаем тестируемую функцию
    result = await handle_invoice(mock_photo_update, mock_context)
    
    # Проверяем, что функция вернула правильное состояние
    assert result == CONFIRMATION
    
    # Проверяем, что функции были вызваны с правильными аргументами
    assert mock_extract.called
    assert mock_match.called
    assert mock_conversions.called
    
    # Проверяем, что сообщение было отправлено
    assert mock_photo_update.message.reply_text.called
    
    # Проверяем, что данные были сохранены в контексте
    assert "invoice" in mock_context.user_data
    assert "invoice_id" in mock_context.user_data


@pytest.mark.asyncio
async def test_handle_invoice_not_photo(mock_context):
    """Тест обработки сообщения без фотографии."""
    # Создаем мок обновления без фото
    update = MagicMock(spec=Update)
    update.message = MagicMock(spec=Message)
    update.message.photo = []
    update.message.reply_text = AsyncMock()
    
    # Запускаем тестируемую функцию
    result = await handle_invoice(update, mock_context)
    
    # Проверяем, что функция вернула правильное состояние
    assert result == WAIT_PHOTO
    
    # Проверяем, что сообщение об ошибке было отправлено
    update.message.reply_text.assert_called_once()
    assert "фото" in update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_handle_invoice_callback_confirm(mocker, mock_callback_update, mock_context):
    """Тест обработки подтверждения накладной."""
    # Мокаем функцию отправки в Syrve
    mock_create_invoice = mocker.patch(
        "handlers.invoice_handlers.create_invoice",
        new=AsyncMock(return_value="123456789")
    )
    
    # Запускаем тестируемую функцию
    result = await handle_invoice_callback(mock_callback_update, mock_context)
    
    # Проверяем, что функция вернула правильное состояние
    assert result == WAIT_PHOTO
    
    # Проверяем, что были вызваны нужные функции
    assert mock_callback_update.callback_query.answer.called
    assert mock_create_invoice.called
    
    # Проверяем, что было отправлено сообщение об успешном создании накладной
    mock_callback_update.callback_query.edit_message_text.assert_called()
    last_call_args = mock_callback_update.callback_query.edit_message_text.call_args[0][0]
    assert "успешно создана" in last_call_args
    assert "123456789" in last_call_args
    
    # Проверяем, что данные были очищены из контекста
    assert "invoice" not in mock_context.user_data
    assert "invoice_id" not in mock_context.user_data


@pytest.mark.asyncio
async def test_handle_invoice_callback_edit(mocker, mock_callback_update, mock_context):
    """Тест обработки редактирования накладной."""
    # Изменяем данные callback query
    mock_callback_update.callback_query.data = "edit_items:test_invoice_id"
    
    # Запускаем тестируемую функцию
    result = await handle_invoice_callback(mock_callback_update, mock_context)
    
    # Проверяем, что функция вернула правильное состояние
    assert result == WAIT_PHOTO
    
    # Проверяем, что были вызваны нужные функции
    assert mock_callback_update.callback_query.answer.called
    
    # Проверяем, что было отправлено сообщение о будущей функции
    mock_callback_update.callback_query.edit_message_text.assert_called()
    last_call_args = mock_callback_update.callback_query.edit_message_text.call_args[0][0]
    assert "будет доступна в следующей версии" in last_call_args
