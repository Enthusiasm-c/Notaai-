"""
handlers/confirmation_handlers.py

Обработчики Telegram для подтверждения действий с накладной.
"""

import math
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import CONFIRMATION, FINAL_CONFIRMATION, WAIT_PHOTO, SET_BUYER, SELECT_SUPPLIER
from utils.invoice_processing import format_invoice_for_display, load_suppliers
from services.syrve_service import send_invoice_to_syrve
from utils.configuration import settings
from utils.error_handling import log_error

logger = logging.getLogger(__name__)

SUPPLIERS_PER_PAGE = 10


async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик подтверждения данных.
    """
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data

    if data == "confirm_action":
        confirm_data = context.user_data.get("confirm_data")
        if not confirm_data:
            await query.edit_message_text("❌ Error: no confirmation data found.")
            return WAIT_PHOTO

        action_type = confirm_data.get("type")
        if action_type == "invoice":
            invoice_data = confirm_data.get("data")
            try:
                invoice_id = await send_invoice_to_syrve(
                    invoice_data,
                    settings.syrve_login,
                    settings.syrve_password,
                    settings.syrve_server_url,
                )
                if invoice_id:
                    await query.edit_message_text(f"✅ Invoice successfully sent to Syrve!\n\nID: {invoice_id}")
                    logger.info(f"User {user.id} sent invoice to Syrve")
                    context.user_data.clear()
                    return WAIT_PHOTO
                else:
                    await query.edit_message_text("❌ Failed to send invoice to Syrve. Please try again later.")
                    return CONFIRMATION
            except Exception as e:
                log_error(f"Error sending invoice to Syrve: {e}", e)
                await query.edit_message_text("❌ Error occurred while sending invoice to Syrve.")
                return CONFIRMATION
        else:
            await query.edit_message_text(f"❌ Unknown action type: {action_type}")
            return WAIT_PHOTO

    elif data == "reject_action":
        await query.edit_message_text("❌ Action canceled by user.")
        logger.info(f"User {user.id} canceled action")
        context.user_data.clear()
        return WAIT_PHOTO

    elif data == "final_preview":
        await query.edit_message_text("Preparing final preview...")
        context.user_data.pop("preview_data", None)
        return FINAL_CONFIRMATION

    elif data == "select_supplier":
        await show_supplier_selection(update, context, page=0)
        return SELECT_SUPPLIER

    elif data.startswith("choose_supplier_"):
        supplier_id = data.replace("choose_supplier_", "")
        await handle_supplier_choice(update, context, supplier_id)
        return CONFIRMATION

    elif data.startswith("supplier_page_"):
        page = int(data.replace("supplier_page_", ""))
        await show_supplier_selection(update, context, page)
        return SELECT_SUPPLIER

    elif data == "set_buyer":
        await ask_buyer_input(update, context)
        return SET_BUYER

    else:
        logger.warning(f"Unknown callback data in confirmation handler: {data}")
        return CONFIRMATION


async def show_supplier_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0) -> None:
    """
    Показывает меню выбора поставщика с пагинацией.
    """
    query = update.callback_query
    suppliers = load_suppliers()

    if not suppliers:
        await query.edit_message_text("❌ Suppliers list is empty. Please contact support.")
        return

    total_pages = math.ceil(min(50, len(suppliers)) / SUPPLIERS_PER_PAGE)
    page = max(0, min(page, total_pages - 1))

    start = page * SUPPLIERS_PER_PAGE
    end = min(start + SUPPLIERS_PER_PAGE, min(50, len(suppliers)))
    page_suppliers = suppliers[start:end]

    keyboard = [
        [InlineKeyboardButton(s["name"], callback_data=f"choose_supplier_{s['id']}")]
        for s in page_suppliers
    ]

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"supplier_page_{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"supplier_page_{page + 1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="back_to_edit")])

    await query.edit_message_text(
        f"Select supplier (page {page + 1}/{total_pages}):",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_supplier_choice(update: Update, context: ContextTypes.DEFAULT_TYPE, supplier_id: str) -> None:
    """
    Обрабатывает выбор поставщика.
    """
    query = update.callback_query
    suppliers = load_suppliers()
    supplier_name = next((s["name"] for s in suppliers if s["id"] == supplier_id), "Unknown supplier")

    invoice_data = context.user_data.get("invoice", {})
    invoice_data["supplier_id"] = supplier_id
    invoice_data["supplier_name"] = supplier_name
    invoice_data["supplier_ok"] = True

    formatted_message = format_invoice_for_display(invoice_data)
    keyboard = []  # Можно использовать build_invoice_keyboard из utils

    context.user_data["invoice"] = invoice_data

    await query.edit_message_text(
        formatted_message + "\n\n<i>Supplier updated. Review and confirm when ready.</i>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def ask_buyer_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Запрашивает ввод покупателя.
    """
    query = update.callback_query
    await query.edit_message_text(
        "Please enter the buyer name:\n\n<i>Type any text to set as the buyer name.</i>",
        parse_mode="HTML",
    )
