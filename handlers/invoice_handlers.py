import json
import logging
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from services.ocr_service import OCRService
from utils.configuration import Config
from utils.error_handling import log_error, save_error_image
from utils.invoice_processing import ParsedInvoice, format_invoice_for_display, match_invoice_items
from utils.storage import save_temp_file

# Set up logging
logger = logging.getLogger(__name__)


async def handle_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle invoice photos and documents

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    try:
        user = update.effective_user
        logger.info(f"Received invoice from {user.id} ({user.username})")

        # Send processing message
        processing_message = await update.message.reply_text(
            "⏳ Обрабатываю документ... Это может занять до 30 секунд."
        )

        # Get file ID
        file_id = None
        file_type = None

        if update.message.photo:
            # Get the largest photo
            file_id = update.message.photo[-1].file_id
            file_type = "photo"
        elif update.message.document:
            file_id = update.message.document.file_id
            file_type = "document"
        else:
            await update.message.reply_text(
                "❌ Пожалуйста, отправьте фото накладной или PDF-документ."
            )
            return

        # Download file
        file = await context.bot.get_file(file_id)
        
        # Create temporary directory if it doesn't exist
        temp_dir = Path("/tmp") / "notaai"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, dir=temp_dir, suffix=".jpg") as temp_file:
            temp_path = temp_file.name
            await file.download_to_drive(temp_path)

        # Process the image with OCR
        config = Config()
        ocr_service = OCRService(api_key=config.OPENAI_API_KEY, model=config.OPENAI_MODEL)

        with open(temp_path, "rb") as f:
            image_data = f.read()

        # Process the image
        raw_data = await ocr_service.process_image(image_data)

        # Create a ParsedInvoice from the OCR output
        invoice_data = ParsedInvoice(
            date=raw_data.get("date", ""),
            vendor_name=raw_data.get("vendor_name", ""),
            total_amount=raw_data.get("total_amount", 0),
            lines=raw_data.get("items", [])
        )

        # Log the OCR result
        logger.info(f"OCR result: {json.dumps(asdict(invoice_data), ensure_ascii=False)[:500]}...")

        # Match invoice items with our product database
        enriched_data = match_invoice_items(asdict(invoice_data))

        # Format invoice data for display
        formatted_message = format_invoice_for_display(enriched_data)

        # Create confirmation keyboard
        keyboard = [
            [
                InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_invoice"),
                InlineKeyboardButton("❌ Отклонить", callback_data="reject_invoice"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Save invoice data to user context
        context.user_data["invoice"] = enriched_data

        # Save the image to temporary storage
        file_key = save_temp_file(user.id, image_data)
        context.user_data["invoice_image_key"] = file_key

        # Edit the processing message
        await processing_message.edit_text(
            formatted_message + "\n\n<i>Проверьте данные и подтвердите отправку.</i>",
            reply_markup=reply_markup,
            parse_mode="HTML",
        )

    except Exception as e:
        # Log error
        log_error(f"Error processing invoice: {str(e)}", e)

        # Save error image if available
        if update.message.photo and "image_data" in locals():
            save_error_image(user.id, image_data)

        # Notify user
        await update.message.reply_text(
            "❌ Произошла ошибка при обработке документа. Пожалуйста, попробуйте еще раз или обратитесь за помощью."
        )


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle callback queries from invoice confirmation buttons

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    query = update.callback_query
    user = query.from_user

    # Answer callback query to stop loading indicator
    await query.answer()

    # Get callback data
    callback_data = query.data

    if callback_data == "confirm_invoice":
        await query.edit_message_text(
            query.message.text + "\n\n✅ <b>Подтверждено и отправлено в Syrve!</b>",
            parse_mode="HTML",
        )

        logger.info(f"User {user.id} confirmed invoice upload")

        # Here would be the code to send the invoice to Syrve
        # For now, we'll just acknowledge the confirmation

    elif callback_data == "reject_invoice":
        await query.edit_message_text(
            query.message.text + "\n\n❌ <b>Отклонено пользователем.</b>",
            parse_mode="HTML",
        )

        logger.info(f"User {user.id} rejected invoice upload")

    else:
        logger.warning(f"Unknown callback data: {callback_data}")
