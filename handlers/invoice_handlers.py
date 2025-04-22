import datetime
import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import CONFIRMATION, WAIT_PHOTO, user_data
from services.ocr_service import extract
from utils.error_handling import log_error, save_error_image
from utils.invoice_processing import (apply_unit_conversions,
                                      format_invoice_data, match_invoice_items)

# Получаем логгер
logger = logging.getLogger(__name__)


async def process_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик входящих фотографий

    Args:
        update: Входящее обновление
        context: Контекст

    Returns:
        int: Следующее состояние диалога
    """
    user_id = update.effective_user.id

    # Отправляем сообщение о начале обработки
    await update.message.reply_text("📸 Received photo! Processing invoice...")

    try:
        # Получаем файл с наилучшим качеством
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()

        # Сохраняем копию изображения для анализа в случае ошибок
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs("logs/images", exist_ok=True)
        image_path = f"logs/images/invoice_{user_id}_{timestamp}.jpg"
        with open(image_path, "wb") as f:
            f.write(photo_bytes)
        logger.info(f"Saved invoice image to {image_path}")

        # Извлекаем данные из изображения с помощью OCR
        logger.info(f"Starting OCR processing for user {user_id}")
        invoice_data = await extract(photo_bytes)
        logger.info(
            f"OCR processing completed: {len(invoice_data.get('lines', []))} lines extracted"
        )

        # Применяем сопоставления и конвертации
        matched_data = await match_invoice_items(invoice_data)
        logger.info(f"Item matching completed")

        conversions_applied = apply_unit_conversions(matched_data)
        logger.info(f"Unit conversions applied: {len(conversions_applied)} conversions")

        # Сохраняем данные для пользователя
        user_data[user_id] = {
            "invoice_data": invoice_data,
            "matched_data": matched_data,
            "conversions_applied": conversions_applied,
            "current_edit_index": None,  # Для редактирования неопознанных товаров
            "edit_history": [],  # История редактирования для возврата
            "image_path": image_path,  # Путь к сохраненному изображению
        }

        # Подготавливаем сообщение с результатами OCR
        message_text = format_invoice_data(user_data[user_id])

        # Создаем клавиатуру для действий
        keyboard = []

        # Проверяем наличие неопознанных товаров
        unmatched_items = [
            item
            for item in matched_data.get("lines", [])
            if item.get("product_id") is None
        ]

        if unmatched_items:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "Fix Unrecognized Items", callback_data="edit_unmatched"
                    )
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton(
                    "Review & Edit Items", callback_data="select_edit_item"
                )
            ]
        )

        if not unmatched_items:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "Confirm & Preview Final", callback_data="final_preview"
                    )
                ]
            )

        keyboard.append(
            [InlineKeyboardButton("Cancel", callback_data="cancel_process")]
        )

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Отправляем сообщение с извлеченными данными и запрашиваем действие
        await update.message.reply_text(message_text, reply_markup=reply_markup)
        return CONFIRMATION

    except Exception as e:
        error_msg = f"Error processing photo: {e}"
        log_error(error_msg, exc_info=True)

        # Сохраняем изображение, вызвавшее ошибку
        save_error_image(user_id, photo_bytes)

        await update.message.reply_text(
            f"❌ An error occurred while processing the photo: {str(e)}\n"
            "Please try sending the photo again or use a clearer image."
        )
        return WAIT_PHOTO
