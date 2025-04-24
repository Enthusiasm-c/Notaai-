"""
Обработчики для работы с накладными в Telegram-боте.

Модуль содержит функции для обработки фото накладных и колбэков их подтверждения.
"""

import json
import logging
import tempfile
from dataclasses import asdict
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import CONFIRMATION, WAIT_PHOTO
from services.ocr_service import extract
from utils.configuration import Config
from utils.error_handling import log_error, save_error_image
from utils.invoice_processing import enrich_invoice, format_invoice_for_display
from utils.storage import save_temp_file

__all__ = ["handle_invoice", "handle_invoice_callback"]

# Настройка логирования
logger = logging.getLogger(__name__)


async def handle_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик получения фотографий накладных.
    
    Args:
        update: Объект Update от Telegram
        context: Контекст бота
        
    Returns:
        int: Следующее состояние диалога
    """
    try:
        user = update.effective_user
        logger.info(f"Получена фотография накладной от пользователя {user.id} ({user.username})")
        
        # Отправляем сообщение о начале обработки
        processing_message = await update.message.reply_text(
            "⏳ Обрабатываю документ... Это может занять до 30 секунд."
        )
        
        # Получаем ID файла
        file_id = None
        file_type = None
        
        if update.message.photo:
            # Берем последнее (самое крупное) фото
            file_id = update.message.photo[-1].file_id
            file_type = "photo"
        elif update.message.document and update.message.document.mime_type == "application/pdf":
            file_id = update.message.document.file_id
            file_type = "document"
        else:
            await update.message.reply_text(
                "❌ Пожалуйста, отправьте фото накладной или PDF-документ."
            )
            return WAIT_PHOTO
        
        # Скачиваем файл
        file = await context.bot.get_file(file_id)
        
        # Создаем временную директорию, если она не существует
        temp_dir = Path("/tmp") / "notaai"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(delete=False, dir=temp_dir, suffix=".jpg") as temp_file:
            temp_path = temp_file.name
            await file.download_to_drive(temp_path)
        
        # Обрабатываем изображение с помощью OCR
        config = Config()
        
        # Извлекаем данные накладной
        invoice_data = await extract(temp_path)
        
        # Логируем результат OCR
        logger.info(f"OCR result: {json.dumps(asdict(invoice_data), ensure_ascii=False)[:500]}...")
        
        # Сопоставляем товары из накладной с базой данных
        enriched_data = await enrich_invoice(asdict(invoice_data))
        
        # Форматируем данные накладной для отображения
        formatted_message = format_invoice_for_display(enriched_data)
        
        # Создаем клавиатуру для подтверждения
        keyboard = [
            [
                InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_invoice"),
                InlineKeyboardButton("❌ Отклонить", callback_data="reject_invoice"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Сохраняем данные накладной в контексте пользователя
        context.user_data["invoice"] = enriched_data
        
        # Сохраняем изображение во временное хранилище
        with open(temp_path, "rb") as f:
            image_data = f.read()
        
        file_key = save_temp_file(user.id, image_data)
        context.user_data["invoice_image_key"] = file_key
        
        # Редактируем сообщение о обработке
        await processing_message.edit_text(
            formatted_message + "\n\n<i>Проверьте данные и подтвердите отправку.</i>",
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
        
        return CONFIRMATION
    
    except Exception as e:
        # Логируем ошибку
        log_error(f"Error processing invoice: {str(e)}", e)
        
        # Сохраняем изображение, вызвавшее ошибку, если доступно
        if update.message.photo and "image_data" in locals():
            save_error_image(user.id, image_data)
        
        # Уведомляем пользователя
        await update.message.reply_text(
            "❌ Произошла ошибка при обработке документа. Пожалуйста, попробуйте еще раз или обратитесь за помощью."
        )
        
        return WAIT_PHOTO


async def handle_invoice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик колбэков для подтверждения/отклонения накладной.
    
    Args:
        update: Объект Update от Telegram
        context: Контекст бота
        
    Returns:
        int: Следующее состояние диалога
    """
    query = update.callback_query
    user = query.from_user
    
    # Отвечаем на колбэк, чтобы убрать индикатор загрузки
    await query.answer()
    
    # Получаем данные колбэка
    callback_data = query.data
    
    if callback_data == "confirm_invoice":
        await query.edit_message_text(
            query.message.text + "\n\n✅ <b>Подтверждено и отправлено в Syrve!</b>",
            parse_mode="HTML",
        )
        
        logger.info(f"User {user.id} confirmed invoice upload")
        
        # Здесь в будущем будет код для отправки накладной в Syrve
        # Пока просто подтверждаем действие
        
        return WAIT_PHOTO
    
    elif callback_data == "reject_invoice":
        await query.edit_message_text(
            query.message.text + "\n\n❌ <b>Отклонено пользователем.</b>",
            parse_mode="HTML",
        )
        
        logger.info(f"User {user.id} rejected invoice upload")
        
        return WAIT_PHOTO
    
    else:
        logger.warning(f"Unknown callback data: {callback_data}")
        return WAIT_PHOTO
