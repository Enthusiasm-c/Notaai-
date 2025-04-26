"""
handlers/manual_item_handlers.py

Обработчики для ручного сопоставления товаров и добавления новых продуктов.
"""

import datetime
import json
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import ADD_NEW_ITEM, CONFIRMATION, EDIT_ITEM, WAIT_PHOTO
from utils.learning import save_learned_mapping
from utils.match import get_product_by_id, match
from utils.error_handling import log_error
from utils.invoice_processing import format_invoice_for_display

logger = logging.getLogger(__name__)


async def handle_manual_item_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработка ручного ввода названия товара пользователем.
    """
    try:
        user_id = update.effective_user.id

        if user_id not in context.user_data:
            await update.message.reply_text("Error: Invoice data not found.")
            return WAIT_PHOTO

        if "awaiting_item_name" not in context.user_data:
            await update.message.reply_text("Error: No item being edited.")
            return WAIT_PHOTO

        entered_name = update.message.text.strip()
        item_index = context.user_data["awaiting_item_name"]["item_index"]
        original_name = context.user_data["awaiting_item_name"]["original_name"]

        # Проверяем существование товара
        exists, product_id = await check_product_exists(entered_name)

        if exists and product_id:
            # Обновляем данные
            context.user_data["invoice"]["items"][item_index].update({
                "product_id": product_id,
                "match_score": 1.0,
                "manual_name": entered_name,
                "match_status": "matched",
                "is_valid": True,
            })
            save_learned_mapping(original_name, product_id)

            await update.message.reply_text(
                f"✅ Product '{entered_name}' found and matched successfully."
            )
        else:
            keyboard = [
                [
                    InlineKeyboardButton(
                        "Yes, add as new",
                        callback_data=f"confirm_manual_new:{item_index}:{entered_name}",
                    ),
                    InlineKeyboardButton(
                        "No, try again",
                        callback_data=f"retry_manual:{item_index}",
                    ),
                ]
            ]
            await update.message.reply_text(
                f"❓ Product '{entered_name}' not found in database.\n"
                "Would you like to add it as a new product?",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            context.user_data["awaiting_item_name"]["entered_name"] = entered_name
            return ADD_NEW_ITEM

        del context.user_data["awaiting_item_name"]
        return CONFIRMATION

    except Exception as e:
        log_error(f"Error in manual item entry: {e}", e)
        await update.message.reply_text(
            "❌ An error occurred. Please try again or /cancel."
        )
        return WAIT_PHOTO


async def handle_manual_entry_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработка callback'ов при ручном вводе товара.
    """
    try:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id

        if user_id not in context.user_data:
            await query.edit_message_text("Error: Invoice data not found.")
            return WAIT_PHOTO

        if query.data.startswith("confirm_manual_new:"):
            parts = query.data.split(":")
            item_index = int(parts[1])
            entered_name = parts[2] if len(parts) > 2 else context.user_data["awaiting_item_name"].get("entered_name", "")
            original_name = context.user_data["awaiting_item_name"]["original_name"]

            new_product_id = f"manual_new_{item_index}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            context.user_data["invoice"]["items"][item_index].update({
                "product_id": new_product_id,
                "match_score": 1.0,
                "manual_name": entered_name,
                "match_status": "matched",
                "is_valid": True,
            })
            save_learned_mapping(original_name, new_product_id)

            await query.edit_message_text(f"✅ Item '{entered_name}' added as new and saved.")
            del context.user_data["awaiting_item_name"]
            return CONFIRMATION

        elif query.data.startswith("retry_manual:"):
            item_index = int(query.data.split(":")[1])
            item_name = context.user_data["invoice"]["items"][item_index].get("name", "Unknown item")
            await query.edit_message_text(
                f"Please try entering a different name for '{item_name}'."
            )
            context.user_data["awaiting_item_name"] = {
                "item_index": item_index,
                "original_name": item_name,
            }
            return ADD_NEW_ITEM

        elif query.data == "cancel_process":
            context.user_data.clear()
            await query.edit_message_text("Operation canceled. Send a new invoice photo.")
            return WAIT_PHOTO

        else:
            return ADD_NEW_ITEM

    except Exception as e:
        log_error(f"Error in manual entry callback: {e}", e)
        await update.callback_query.edit_message_text(
            "❌ An error occurred. Please try again or /cancel."
        )
        return WAIT_PHOTO
