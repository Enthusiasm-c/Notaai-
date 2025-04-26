"""
handlers/conversion_handlers.py

Обработчики для настройки и применения конвертации единиц измерения.
"""

import datetime
import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import SET_CONVERSION, EDIT_ITEM, WAIT_PHOTO
from utils.learning import save_unit_conversion
from utils.error_handling import log_error

logger = logging.getLogger(__name__)


async def handle_conversion_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработка ввода данных для конвертации единиц измерения.
    """
    try:
        user_id = update.effective_user.id

        if user_id not in context.user_data:
            await update.message.reply_text("Error: Invoice data not found.")
            return WAIT_PHOTO

        if "setting_conversion" not in context.user_data:
            await update.message.reply_text("Error: No conversion being set.")
            return WAIT_PHOTO

        input_text = update.message.text.strip()
        conversion_data = context.user_data["setting_conversion"]
        current_step = conversion_data.get("step")

        if current_step == "target_unit":
            target_unit = input_text.lower()
            conversion_data["target_unit"] = target_unit
            conversion_data["step"] = "conversion_factor"

            await update.message.reply_text(
                f"Setting unit conversion from {conversion_data['source_unit']} to {target_unit}.\n\n"
                f"Please enter the conversion factor (e.g., 0.5 means 1 {conversion_data['source_unit']} = 0.5 {target_unit}):"
            )
            return SET_CONVERSION

        elif current_step == "conversion_factor":
            try:
                factor = float(input_text.replace(",", "."))
                item_index = conversion_data["item_index"]
                product_name = conversion_data["product_name"]
                source_unit = conversion_data["source_unit"]
                target_unit = conversion_data["target_unit"]

                matched_data = context.user_data["invoice"]["items"]
                product_id = matched_data[item_index].get("product_id")
                if not product_id:
                    product_id = f"temp_{item_index}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
                    matched_data[item_index]["product_id"] = product_id

                save_unit_conversion(source_unit, target_unit, factor)

                qty = matched_data[item_index].get("quantity", 0)
                matched_data[item_index]["original_qty"] = qty
                matched_data[item_index]["original_unit"] = source_unit
                matched_data[item_index]["quantity"] = qty * factor
                matched_data[item_index]["unit"] = target_unit
                matched_data[item_index]["conversion_applied"] = True

                if "conversions_applied" not in context.user_data:
                    context.user_data["conversions_applied"] = []

                context.user_data["conversions_applied"].append({
                    "line_index": item_index,
                    "product_name": product_name,
                    "product_id": product_id,
                    "original_qty": qty,
                    "original_unit": source_unit,
                    "converted_qty": qty * factor,
                    "converted_unit": target_unit,
                    "conversion_factor": factor,
                })

                await update.message.reply_text(
                    f"✅ Unit conversion set successfully!\n\n"
                    f"1 {source_unit} = {factor} {target_unit}\n\n"
                    f"This conversion will be applied automatically in future."
                )

                del context.user_data["setting_conversion"]

                # Здесь можно добавить логику для дальнейших действий, например, показать меню
                return EDIT_ITEM

            except ValueError:
                await update.message.reply_text(
                    "Please enter a valid number for the conversion factor (e.g., 0.5, 2, 1.25)."
                )
                return SET_CONVERSION

        else:
            return EDIT_ITEM

    except Exception as e:
        log_error(f"Error in handle_conversion_entry: {e}", e)
        await update.message.reply_text(
            "❌ An error occurred. Please try again or /cancel."
        )
        return WAIT_PHOTO


async def handle_conversion_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработка callback'ов при настройке конвертации единиц.
    """
    try:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id

        if user_id not in context.user_data:
            await query.edit_message_text("Error: Invoice data not found.")
            return WAIT_PHOTO

        if query.data == "cancel_process":
            context.user_data.clear()
            await query.edit_message_text("Operation canceled. Send a new invoice photo.")
            return WAIT_PHOTO

        elif query.data == "back_to_edit" and "setting_conversion" in context.user_data:
            item_index = context.user_data["setting_conversion"].get("item_index")
            if item_index is not None:
                del context.user_data["setting_conversion"]
                # Здесь можно вызвать функцию показа меню редактирования товара
                await query.edit_message_text(f"Returning to edit item #{item_index + 1} - feature coming soon.")
                return EDIT_ITEM

        return SET_CONVERSION

    except Exception as e:
        log_error(f"Error in handle_conversion_callback: {e}", e)
        await update.callback_query.edit_message_text(
            "❌ An error occurred. Please try again or /cancel."
        )
        return WAIT_PHOTO
