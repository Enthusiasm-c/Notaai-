"""
handlers/invoice_handlers.py

Обработчики Telegram для работы с накладными.
"""

import logging
from pathlib import Path

from telegram import InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import CONFIRMATION, WAIT_PHOTO
from services.ocr_service import extract
from utils.invoice_processing import enrich_invoice, format_invoice_for_display, ensure_result
from utils.invoice_keyboard import build_invoice_keyboard
from utils.storage import save_temp_file
from utils.error_handling import log_error, save_error_image

logger = logging.getLogger(__name__)


async def handle_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик получения фото накладной.
    """
    try:
        user = update.effective_user
        logger.info(f"Received invoice photo from user {user.id}")

        if not update.message or not update.message.photo:
            await update.message.reply_text("❌ Please send a photo of the invoice.")
            return WAIT_PHOTO

        # Берём самый большой размер фото
        file_id = update.message.photo[-1].file_id
        file = await context.bot.get_file(file_id)

        # Сохраняем во временный файл
        temp_dir = Path("/tmp/notaai")
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = temp_dir / f"{user.id}_{file_id}.jpg"
        await file.download_to_drive(str(temp_path))

        # OCR распознавание
        parsed = await extract(str(temp_path))
        if not parsed:
            await update.message.reply_text("❌ Failed to extract data from image. Please try again.")
            return WAIT_PHOTO

        # Enrich и унификация данных
        enriched = await enrich_invoice(parsed.__dict__)
        invoice_data = await ensure_result(enriched)

        # Форматируем сообщение и клавиатуру
        formatted_message = format_invoice_for_display(invoice_data)
        keyboard = build_invoice_keyboard(invoice_data)

        # Сохраняем данные в контексте
        context.user_data["invoice"] = invoice_data

        # Сохраняем изображение временно
        with open(temp_path, "rb") as f:
            image_bytes = f.read()
        file_key = await save_temp_file(user.id, image_bytes)
        context.user_data["invoice_image_key"] = file_key

        # Отправляем сообщение с клавиатурой
        await update.message.reply_text(
            formatted_message + "\n\n<i>Review the data and fix any issues.</i>",
            reply_markup=keyboard,
            parse_mode="HTML",
        )

        return CONFIRMATION

    except Exception as e:
        log_error(f"Error processing invoice: {e}", e)
        if update.message and "image_bytes" in locals():
            save_error_image(user.id, image_bytes)
        await update.message.reply_text(
            "❌ An error occurred while processing the invoice. Please try again."
        )
        return WAIT_PHOTO


async def handle_invoice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик callback'ов из клавиатуры накладной.
    """
    query = update.callback_query
    await query.answer()
    user = query.from_user

    data = query.data

    if data == "send_to_syrve":
        invoice_data = context.user_data.get("invoice")
        if not invoice_data:
            await query.edit_message_text("❌ Invoice data not found.")
            return WAIT_PHOTO

        from services.syrve_service import send_invoice_to_syrve
        from utils.configuration import settings

        try:
            invoice_id = await send_invoice_to_syrve(
                invoice_data,
                settings.syrve_login,
                settings.syrve_password,
                settings.syrve_server_url,
            )
            if invoice_id:
                await query.edit_message_text("✅ Invoice sent to Syrve ✔️")
                logger.info(f"User {user.id} sent invoice to Syrve")
                context.user_data.clear()
                return WAIT_PHOTO
            else:
                await query.edit_message_text("❌ Failed to send invoice to Syrve. Please try again.")
                return CONFIRMATION
        except Exception as e:
            log_error(f"Error sending invoice to Syrve: {e}", e)
            await query.edit_message_text("❌ Error occurred while sending invoice to Syrve.")
            return CONFIRMATION

    elif data == "select_supplier":
        # Здесь можно вызвать обработчик выбора поставщика (реализовать отдельно)
        await query.edit_message_text("Supplier selection not implemented yet.")
        return CONFIRMATION

    elif data == "set_buyer":
        # Здесь можно вызвать обработчик ввода покупателя (реализовать отдельно)
        await query.edit_message_text("Buyer input not implemented yet.")
        return CONFIRMATION

    elif data.startswith("fix_item_"):
        # Обработка исправления конкретного item (реализовать отдельно)
        await query.edit_message_text("Item fixing not implemented yet.")
        return CONFIRMATION

    else:
        logger.warning(f"Unknown callback data: {data}")
        return CONFIRMATION
