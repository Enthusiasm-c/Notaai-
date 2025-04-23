"""
Обработчики для работы с накладными.
"""

import logging
import os
import uuid

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import CONFIRMATION, WAIT_PHOTO
from services.ocr_service import extract
from services.syrve_service import create_invoice
from utils.error_handling import log_error
from utils.invoice_processing import apply_unit_conversions, match_invoice_items

# Получаем логгер
logger = logging.getLogger(__name__)


async def handle_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик для получения и обработки фото накладной.

    Args:
        update: Входящее обновление от Telegram
        context: Контекст бота

    Returns:
        int: Следующее состояние диалога
    """
    # Проверяем, что это фото
    if not update.message or not update.message.photo:
        await update.message.reply_text("🖼 Пришлите фото накладной...")
        return WAIT_PHOTO

    # Сообщаем пользователю, что начали обработку
    await update.message.reply_text("📸 Получил фото! Обрабатываю накладную...")

    try:
        # Получаем файл с наилучшим качеством
        photo = update.message.photo[-1]
        photo_file = await photo.get_file()
        
        # Создаем директорию для временных файлов, если её нет
        os.makedirs("tmp", exist_ok=True)
        
        # Генерируем имя файла и сохраняем фото
        photo_path = f"tmp/invoice_{update.effective_chat.id}_{uuid.uuid4()}.jpg"
        await photo_file.download_to_drive(photo_path)
        
        logger.info("Saved photo to %s", photo_path)
        
        # Извлекаем данные из фото с помощью OCR
        logger.info("Starting OCR extraction for chat %s", update.effective_chat.id)
        invoice_data = await extract(photo_path)
        
        if not invoice_data:
            await update.message.reply_text(
                "❌ Не удалось распознать накладную. Пожалуйста, попробуйте еще раз с более "
                "четким изображением."
            )
            return WAIT_PHOTO
            
        # Логируем количество найденных позиций
        items_count = len(invoice_data.items)
        logger.info("OCR parsed %d items for chat %s", items_count, update.effective_chat.id)
        
        if items_count == 0:
            await update.message.reply_text(
                "📄 Не найдены товары в накладной. Пожалуйста, убедитесь, что изображение "
                "содержит таблицу товаров."
            )
            return WAIT_PHOTO
            
        # Сопоставляем товары с базой данных
        matched_data = await match_invoice_items(invoice_data)
        logger.info("Matched items with database")
        
        # Применяем конвертации единиц измерения
        conversions = apply_unit_conversions(matched_data)
        logger.info("Applied %d unit conversions", len(conversions))
        
        # Сохраняем данные в контексте для дальнейшего использования
        context.user_data["invoice"] = matched_data
        
        # Форматируем превью для пользователя
        preview_text = format_invoice_preview(matched_data)
        
        # Генерируем уникальный идентификатор для callback_data
        invoice_id = str(uuid.uuid4())
        context.user_data["invoice_id"] = invoice_id
        
        # Создаем клавиатуру с кнопками подтверждения/редактирования
        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Подтвердить", callback_data=f"confirm_invoice:{invoice_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "✏️ Исправить позиции", callback_data=f"edit_items:{invoice_id}"
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем превью пользователю
        await update.message.reply_text(preview_text, reply_markup=reply_markup)
        
        # Удаляем временный файл
        try:
            os.remove(photo_path)
            logger.debug("Removed temporary file %s", photo_path)
        except Exception as e:
            logger.warning("Failed to remove temporary file: %s", e)
        
        return CONFIRMATION
        
    except Exception as e:
        log_error(f"Error processing invoice photo: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Произошла ошибка при обработке фото. Пожалуйста, попробуйте еще раз."
        )
        return WAIT_PHOTO


async def handle_invoice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик для кнопок подтверждения/редактирования накладной.

    Args:
        update: Входящее обновление от Telegram
        context: Контекст бота

    Returns:
        int: Следующее состояние диалога
    """
    query = update.callback_query
    await query.answer()
    
    # Проверяем, что в контексте есть данные накладной
    if "invoice" not in context.user_data:
        await query.edit_message_text("❌ Данные накладной не найдены. Начните сначала.")
        return WAIT_PHOTO
    
    # Обрабатываем подтверждение накладной
    if query.data.startswith("confirm_invoice:"):
        invoice_id = query.data.split(":", 1)[1]
        
        # Проверяем соответствие ID
        if context.user_data.get("invoice_id") != invoice_id:
            logger.warning(
                "Invoice ID mismatch: %s != %s", 
                context.user_data.get("invoice_id"), 
                invoice_id
            )
            await query.edit_message_text(
                "❌ Неверный идентификатор накладной. Пожалуйста, начните сначала."
            )
            return WAIT_PHOTO
            
        # Отправляем накладную в Syrve
        await query.edit_message_text("⏳ Отправляю накладную в Syrve...")
        
        try:
            # Получаем данные накладной
            invoice_data = context.user_data["invoice"]
            
            # Отправляем в Syrve
            doc_id = await create_invoice(invoice_data)
            
            if doc_id:
                logger.info("Invoice successfully created in Syrve with ID: %s", doc_id)
                await query.edit_message_text(
                    f"📥 Накладная №{doc_id} успешно создана в Syrve."
                )
            else:
                logger.error("Failed to create invoice in Syrve")
                await query.edit_message_text(
                    "❌ Не удалось создать накладную в Syrve. Пожалуйста, попробуйте позже."
                )
                
            # Очищаем данные накладной
            context.user_data.pop("invoice", None)
            context.user_data.pop("invoice_id", None)
            
            return WAIT_PHOTO
            
        except Exception as e:
            log_error(f"Error sending invoice to Syrve: {e}", exc_info=True)
            await query.edit_message_text(
                "❌ Произошла ошибка при отправке накладной. Пожалуйста, попробуйте позже."
            )
            return WAIT_PHOTO
    
    # Обрабатываем редактирование накладной
    elif query.data.startswith("edit_items:"):
        # Пока просто показываем сообщение
        await query.edit_message_text(
            "🔧 Функция редактирования позиций будет доступна в следующей версии."
            "\n\nОтправьте новое фото накладной."
        )
        return WAIT_PHOTO
    
    # Если callback_data неизвестен
    else:
        logger.warning("Unknown callback_data: %s", query.data)
        await query.edit_message_text(
            "❌ Неизвестная команда. Пожалуйста, отправьте фото накладной."
        )
        return WAIT_PHOTO


def format_invoice_preview(invoice_data: dict) -> str:
    """
    Форматирует превью накладной для отображения пользователю.

    Args:
        invoice_data: Данные накладной

    Returns:
        str: Отформатированное превью
    """
    supplier = invoice_data.get("supplier", "Неизвестный поставщик")
    total = invoice_data.get("total", 0)
    
    # Формируем заголовок
    preview = f"Поставщик: {supplier}\n"
    preview += "-" * 41 + "\n"
    
    # Добавляем строки товаров
    for i, item in enumerate(invoice_data.get("lines", [])):
        name = item.get("name", "Неизвестный товар")
        qty = item.get("qty", 0)
        unit = item.get("unit", "")
        price = item.get("price", 0)
        
        # Форматируем строку товара
        line_num = i + 1
        item_total = qty * price
        
        # Используем ljust для выравнивания колонок
        name_field = name[:15].ljust(15)  # Ограничиваем длину названия
        qty_field = f"{qty:.2f} {unit}".ljust(10)
        price_field = f"{price}"
        
        line = f"{line_num}. {name_field} {qty_field} × {price_field} = {item_total:.2f}\n"
        preview += line
    
    # Добавляем итоговую сумму
    preview += f"\nИтого по накладной: {total:.2f} ₽"
    
    return preview
