import json
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from services.syrve_service import SyrveService
from utils.invoice_processing import format_invoice_for_display
from utils.match import get_product_by_id

# Set up logging
logger = logging.getLogger(__name__)


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle callback queries from inline keyboards

    Args:
        update: Update object
        context: Context object
    """
    query = update.callback_query
    await query.answer()  # Acknowledge the button click

    # Get callback data
    try:
        data = json.loads(query.data)
        action = data.get("action")

        # Process based on action
        if action == "confirm_invoice":
            await handle_invoice_confirmation(update, context, data)
        elif action == "reject_invoice":
            await handle_invoice_rejection(update, context, data)
        elif action == "edit_invoice":
            await handle_invoice_edit(update, context, data)
        else:
            logger.warning(f"Unknown action in callback query: {action}")
            await query.edit_message_text("Извините, произошла ошибка при обработке запроса.")
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in callback query data: {query.data}")
        await query.edit_message_text("Извините, произошла ошибка при обработке запроса.")
    except Exception as e:
        logger.error(f"Error handling callback query: {str(e)}", exc_info=True)
        await query.edit_message_text("Извините, произошла ошибка при обработке запроса.")


async def handle_invoice_confirmation(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data: dict
) -> None:
    """
    Handle invoice confirmation

    Args:
        update: Update object
        context: Context object
        data: Callback data
    """
    query = update.callback_query
    invoice_id = data.get("invoice_id")

    # Get invoice data from user_data
    invoice_data = context.user_data.get("pending_invoice")

    if not invoice_data:
        logger.warning("No pending invoice found for confirmation")
        await query.edit_message_text(
            "Извините, данные накладной не найдены. Пожалуйста, загрузите накладную заново."
        )
        return

    # Get Syrve service
    syrve_service = context.bot_data.get("syrve_service")
    if not syrve_service:
        logger.error("Syrve service not initialized")
        await query.edit_message_text(
            "Извините, сервис Syrve недоступен. Пожалуйста, обратитесь к администратору."
        )
        return

    try:
        # Send invoice to Syrve
        logger.info("Sending invoice to Syrve")
        syrve_invoice_id = await syrve_service.create_invoice(invoice_data)

        if syrve_invoice_id:
            # Clear pending invoice
            context.user_data.pop("pending_invoice", None)

            # Success message
            await query.edit_message_text(
                "Накладная успешно отправлена в Syrve! ✅\n\n"
                f"Идентификатор накладной: {syrve_invoice_id}",
                parse_mode="HTML",
            )
            logger.info(f"Invoice successfully sent to Syrve with ID: {syrve_invoice_id}")
        else:
            # Error message
            await query.edit_message_text(
                "Не удалось отправить накладную в Syrve. Пожалуйста, попробуйте еще раз или обратитесь к администратору.",
                reply_markup=create_retry_keyboard(invoice_id),
            )
            logger.error("Failed to create invoice in Syrve")
    except Exception as e:
        logger.error(f"Error sending invoice to Syrve: {str(e)}", exc_info=True)
        await query.edit_message_text(
            "Произошла ошибка при отправке накладной в Syrve. Пожалуйста, попробуйте еще раз или обратитесь к администратору.",
            reply_markup=create_retry_keyboard(invoice_id),
        )


async def handle_invoice_rejection(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data: dict
) -> None:
    """
    Handle invoice rejection

    Args:
        update: Update object
        context: Context object
        data: Callback data
    """
    query = update.callback_query

    # Clear pending invoice
    context.user_data.pop("pending_invoice", None)

    # Inform user
    await query.edit_message_text(
        "Накладная отклонена. Вы можете загрузить другую накладную или отредактировать текущую.",
        reply_markup=create_new_invoice_keyboard(),
    )
    logger.info("Invoice rejected by user")


async def handle_invoice_edit(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data: dict
) -> None:
    """
    Handle invoice edit request

    Args:
        update: Update object
        context: Context object
        data: Callback data
    """
    query = update.callback_query

    # Inform user that editing is not implemented yet
    await query.edit_message_text(
        "Редактирование накладной будет доступно в следующей версии. Пожалуйста, отклоните накладную и загрузите новую.",
        reply_markup=create_confirm_reject_keyboard(data.get("invoice_id", "")),
    )
    logger.info("User requested invoice edit (not implemented yet)")


def create_confirm_reject_keyboard(invoice_id: str) -> InlineKeyboardMarkup:
    """
    Create confirmation keyboard

    Args:
        invoice_id: Invoice ID

    Returns:
        InlineKeyboardMarkup: Confirmation keyboard
    """
    confirm_data = json.dumps({"action": "confirm_invoice", "invoice_id": invoice_id})
    reject_data = json.dumps({"action": "reject_invoice", "invoice_id": invoice_id})
    edit_data = json.dumps({"action": "edit_invoice", "invoice_id": invoice_id})

    keyboard = [
        [
            InlineKeyboardButton("Подтвердить ✅", callback_data=confirm_data),
            InlineKeyboardButton("Отклонить ❌", callback_data=reject_data),
        ],
        [InlineKeyboardButton("Редактировать 🖊", callback_data=edit_data)],
    ]

    return InlineKeyboardMarkup(keyboard)


def create_retry_keyboard(invoice_id: str) -> InlineKeyboardMarkup:
    """
    Create retry keyboard

    Args:
        invoice_id: Invoice ID

    Returns:
        InlineKeyboardMarkup: Retry keyboard
    """
    retry_data = json.dumps({"action": "confirm_invoice", "invoice_id": invoice_id})
    cancel_data = json.dumps({"action": "reject_invoice", "invoice_id": invoice_id})

    keyboard = [
        [
            InlineKeyboardButton("Повторить ⤴️", callback_data=retry_data),
            InlineKeyboardButton("Отменить ❌", callback_data=cancel_data),
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


def create_new_invoice_keyboard() -> InlineKeyboardMarkup:
    """
    Create new invoice keyboard

    Returns:
        InlineKeyboardMarkup: New invoice keyboard
    """
    keyboard = [[InlineKeyboardButton("Загрузить новую накладную 📄", callback_data="new_invoice")]]

    return InlineKeyboardMarkup(keyboard)


async def send_invoice_confirmation(
    update: Update, context: ContextTypes.DEFAULT_TYPE, invoice_data: dict
) -> None:
    """
    Send invoice confirmation message

    Args:
        update: Update object
        context: Context object
        invoice_data: Invoice data
    """
    # Store invoice data in user_data
    context.user_data["pending_invoice"] = invoice_data

    # Generate a unique ID for this invoice
    invoice_id = str(hash(json.dumps(invoice_data)))

    # Format invoice data for display
    formatted_invoice = format_invoice_for_display(invoice_data)

    # Create confirmation message
    message = (
        "📝 <b>Подтверждение накладной</b>\n\n"
        f"{formatted_invoice}\n\n"
        "Пожалуйста, проверьте данные и подтвердите отправку в Syrve."
    )

    # Send message with confirmation buttons
    await update.effective_chat.send_message(
        text=message, parse_mode="HTML", reply_markup=create_confirm_reject_keyboard(invoice_id)
    )

    logger.info("Sent invoice confirmation message")
