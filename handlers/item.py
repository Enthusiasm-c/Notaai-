"""
handlers/item_handlers.py

Обработчики Telegram для работы с товарами в накладных.
"""

import asyncio
import datetime
import json
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import ADD_NEW_ITEM, CONFIRMATION, EDIT_ITEM, SELECT_EDIT_ITEM, SET_CONVERSION, WAIT_PHOTO
from utils.invoice_processing import format_invoice_for_display
from utils.learning import save_learned_mapping, save_unit_conversion
from utils.error_handling import log_error

logger = logging.getLogger(__name__)


async def display_item_selection(query, user_id):
    """
    Показывает список товаров для выбора редактирования.
    """
    user_data = query._bot_data.get("user_data", {})
    matched_data = user_data.get(user_id, {}).get("invoice", {}).get("items", [])

    message_text = "📋 Select an item to edit:\n\n"
    keyboard = []

    for i, item in enumerate(matched_data):
        name = item.get("name", "Unknown item")
        if len(name) > 30:
            name = name[:27] + "..."
        message_text += f"{i+1}. {name}\n"
        keyboard.append([InlineKeyboardButton(f"Edit item #{i+1}", callback_data=f"edit_item:{i}")])

    keyboard.append([
        InlineKeyboardButton("Back to Main", callback_data="back_to_main"),
        InlineKeyboardButton("Cancel", callback_data="cancel_process"),
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=message_text, reply_markup=reply_markup)


async def handle_item_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик выбора товара для редактирования.
    """
    try:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id

        if user_id not in context.user_data or "invoice" not in context.user_data:
            await query.edit_message_text("Error: Invoice data not found.")
            return WAIT_PHOTO

        if query.data == "back_to_main":
            invoice_data = context.user_data["invoice"]
            formatted_message = format_invoice_for_display(invoice_data)
            # Генерация клавиатуры для главного меню (можно вынести в utils)
            keyboard = []  # TODO: добавить кнопки
            await query.edit_message_text(text=formatted_message, reply_markup=InlineKeyboardMarkup(keyboard))
            return CONFIRMATION

        elif query.data == "cancel_process":
            context.user_data.clear()
            await query.edit_message_text("Operation canceled. Send a new invoice photo.")
            return WAIT_PHOTO

        elif query.data.startswith("edit_item:"):
            item_index = int(query.data.split(":")[1])
            context.user_data["current_edit_index"] = item_index
            # TODO: показать меню редактирования товара
            await query.edit_message_text(f"Editing item #{item_index + 1} - feature coming soon.")
            return EDIT_ITEM

        else:
            return SELECT_EDIT_ITEM

    except Exception as e:
        log_error(f"Error in handle_item_selection: {e}", e)
        await update.callback_query.edit_message_text("❌ An error occurred. Please try again.")
        return WAIT_PHOTO


# Далее можно добавить обработчики для ручного ввода, конвертации и т.д.
# Пока оставляем заглушки или минимальную реализацию.
