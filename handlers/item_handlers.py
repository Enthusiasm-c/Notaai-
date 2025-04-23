import asyncio
import datetime
import json
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import (
    ADD_NEW_ITEM,
    CONFIRMATION,
    EDIT_ITEM,
    SELECT_EDIT_ITEM,
    SET_CONVERSION,
    WAIT_PHOTO,
    user_data,
)
from data.learning import save_learned_mapping, save_unit_conversion
from utils.error_handling import log_error
from utils.invoice_processing import check_product_exists, format_invoice_data

# Получаем логгер
logger = logging.getLogger(__name__)


async def display_item_selection(query, user_id):
    """
    Отображает список товаров для выбора редактирования

    Args:
        query: Callback-запрос
        user_id: ID пользователя
    """
    matched_data = user_data[user_id]["matched_data"]

    message_text = "📋 Select an item to edit:\n\n"

    # Создаем клавиатуру со списком товаров
    keyboard = []

    for i, line in enumerate(matched_data.get("lines", [])):
        line_num = line.get("line", i + 1)
        name = line.get("name", "Unknown item")

        # Добавляем информацию о товаре
        if len(name) > 30:
            name = name[:27] + "..."

        message_text += f"{line_num}. {name}\n"

        # Добавляем кнопку для редактирования
        keyboard.append(
            [InlineKeyboardButton(f"Edit item #{line_num}", callback_data=f"edit_item:{i}")]
        )

    # Добавляем кнопки навигации
    keyboard.append(
        [
            InlineKeyboardButton("Back to Main", callback_data="back_to_main"),
            InlineKeyboardButton("Cancel", callback_data="cancel_process"),
        ]
    )

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text=message_text, reply_markup=reply_markup)


async def handle_item_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик выбора товара для редактирования

    Args:
        update: Входящее обновление
        context: Контекст

    Returns:
        int: Следующее состояние диалога
    """
    try:
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id

        if user_id not in user_data:
            await query.edit_message_text("Error: Invoice data not found.")
            return WAIT_PHOTO

        if query.data == "back_to_main":
            # Возвращаемся к основному экрану
            message_text = format_invoice_data(user_data[user_id])

            # Создаем клавиатуру для действий
            keyboard = []

            # Проверяем наличие неопознанных товаров
            unmatched_items = [
                item
                for item in user_data[user_id]["matched_data"].get("lines", [])
                if item.get("product_id") is None
            ]

            if unmatched_items:
                keyboard.append(
                    [InlineKeyboardButton("Fix Unrecognized Items", callback_data="edit_unmatched")]
                )

            keyboard.append(
                [InlineKeyboardButton("Review & Edit Items", callback_data="select_edit_item")]
            )

            if not unmatched_items:
                keyboard.append(
                    [InlineKeyboardButton("Confirm & Preview Final", callback_data="final_preview")]
                )

            keyboard.append([InlineKeyboardButton("Cancel", callback_data="cancel_process")])

            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(text=message_text, reply_markup=reply_markup)
            return CONFIRMATION

        elif query.data == "cancel_process":
            if user_id in user_data:
                del user_data[user_id]

            await query.edit_message_text(text="Operation canceled. Send a new invoice photo.")
            return WAIT_PHOTO

        elif query.data.startswith("edit_item:"):
            # Получаем индекс товара для редактирования
            item_index = int(query.data.split(":")[1])

            # Сохраняем индекс текущего редактируемого товара
            user_data[user_id]["current_edit_index"] = item_index

            # Сохраняем текущее состояние для возможности возврата
            if "edit_history" not in user_data[user_id]:
                user_data[user_id]["edit_history"] = []

            # Клонируем текущее состояние
            current_state = json.loads(json.dumps(user_data[user_id]["matched_data"]))
            user_data[user_id]["edit_history"].append(current_state)

            # Отображаем информацию о товаре и варианты действий
            await display_item_edit_options(query, user_id, item_index)
            return EDIT_ITEM

        return SELECT_EDIT_ITEM

    except Exception as e:
        error_msg = f"Error in handle_item_selection: {e}"
        log_error(error_msg, exc_info=True)

        try:
            await query.edit_message_text(
                text="❌ An error occurred. Please try again or start over with /cancel."
            )
        except Exception:
            pass

        return WAIT_PHOTO


async def display_item_edit_options(query, user_id, item_index):
    """
    Отображает информацию о товаре и варианты действий

    Args:
        query: Callback-запрос
        user_id: ID пользователя
        item_index: Индекс товара
    """
    matched_data = user_data[user_id]["matched_data"]
    line = matched_data["lines"][item_index]

    line_num = line.get("line", item_index + 1)
    name = line.get("name", "Unknown item")
    qty = line.get("qty", 0)
    unit = line.get("unit", "")
    price = line.get("price", 0)
    product_id = line.get("product_id")

    # Определяем, редактируем неопознанный товар или уже сопоставленный
    is_unrecognized = product_id is None

    # Для неопознанных товаров считаем их количество и текущую позицию
    edit_progress = ""
    unmatched_indices = []
    if is_unrecognized:
        unmatched_indices = [
            i for i, l in enumerate(matched_data.get("lines", [])) if l.get("product_id") is None
        ]
        current_position = unmatched_indices.index(item_index) + 1
        total_unmatched = len(unmatched_indices)
        edit_progress = f"Item {current_position} of {total_unmatched} unrecognized"

    # Создаем сообщение
    message_text = (
        f"Editing item #{line_num}{' (' + edit_progress + ')' if edit_progress else ''}:\n\n"
        f"Name: {name}\n"
        f"Quantity: {qty} {unit}\n"
        f"Price: {price} IDR\n"
    )

    if product_id:
        message_text += f"Status: ✅ Matched with ID: {product_id}\n"
    else:
        message_text += "Status: ❓ Unrecognized\n"

    message_text += "\nSelect action:"

    # Создаем клавиатуру с вариантами действий
    keyboard = []

    # Базовые действия для всех товаров
    keyboard.append(
        [InlineKeyboardButton("Enter correct item", callback_data=f"manual_match:{item_index}")]
    )
    keyboard.append(
        [InlineKeyboardButton("Add as new item", callback_data=f"add_new:{item_index}")]
    )

    # Для неопознанных товаров добавляем кнопку перехода к следующему
    if is_unrecognized and len(unmatched_indices) > 1:
        next_idx = unmatched_indices[
            (unmatched_indices.index(item_index) + 1) % len(unmatched_indices)
        ]
        keyboard.append(
            [
                InlineKeyboardButton(
                    "Skip to next unrecognized",
                    callback_data=f"next_unmatched:{next_idx}",
                )
            ]
        )

    # Кнопка для конвертации единиц измерения
    keyboard.append(
        [InlineKeyboardButton("Set unit conversion", callback_data=f"set_conversion:{item_index}")]
    )

    # Кнопки навигации
    nav_row = []

    # Кнопка возврата к предыдущему шагу, если есть история
    if user_data[user_id].get("edit_history"):
        nav_row.append(InlineKeyboardButton("Previous Step", callback_data="previous_step"))

    # Добавляем кнопки возврата
    if is_unrecognized:
        nav_row.append(InlineKeyboardButton("Back to Main", callback_data="back_to_main"))
    else:
        nav_row.append(InlineKeyboardButton("Back to Item List", callback_data="back_to_selection"))

    if nav_row:
        keyboard.append(nav_row)

    # Кнопка отмены
    keyboard.append([InlineKeyboardButton("Cancel Operation", callback_data="cancel_process")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text=message_text, reply_markup=reply_markup)


async def handle_item_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик действий при редактировании товара

    Args:
        update: Входящее обновление
        context: Контекст

    Returns:
        int: Следующее состояние диалога
    """
    try:
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id

        if user_id not in user_data or user_data[user_id].get("current_edit_index") is None:
            await query.edit_message_text("Error: Editing data not found.")
            return WAIT_PHOTO

        current_index = user_data[user_id]["current_edit_index"]
        matched_data = user_data[user_id]["matched_data"]

        # Ручной ввод названия товара
        if query.data.startswith("manual_match:"):
            item_index = int(query.data.split(":")[1])
            item_name = matched_data["lines"][item_index].get("name", "")

            await query.edit_message_text(
                text=f"Enter the correct item name for '{item_name}'.\n\n"
                "Type the exact name as it appears in your product database."
            )

            # Сохраняем данные для обработчика текстовых сообщений
            context.user_data["awaiting_item_name"] = {
                "item_index": item_index,
                "original_name": item_name,
            }

            return ADD_NEW_ITEM

        # Добавление товара как нового
        elif query.data.startswith("add_new:"):
            item_index = int(query.data.split(":")[1])
            item_name = matched_data["lines"][item_index].get("name", "")

            # Запрашиваем подтверждение
            keyboard = [
                [
                    InlineKeyboardButton(
                        "Yes, add as new", callback_data=f"confirm_add_new:{item_index}"
                    ),
                    InlineKeyboardButton("No, go back", callback_data=f"back_to_edit:{item_index}"),
                ]
            ]

            await query.edit_message_text(
                text=f"Are you sure you want to add '{item_name}' as a new product?\n\n"
                "This will create a new entry in the database.",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

            return EDIT_ITEM

        # Подтверждение добавления нового товара
        elif query.data.startswith("confirm_add_new:"):
            item_index = int(query.data.split(":")[1])
            item_name = matched_data["lines"][item_index].get("name", "")

            # Генерируем новый ID товара
            new_product_id = f"new_{item_index}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            matched_data["lines"][item_index]["product_id"] = new_product_id
            matched_data["lines"][item_index]["match_score"] = 1.0  # Идеальное совпадение

            # Сохраняем сопоставление
            save_learned_mapping(item_name, new_product_id, item_name)

            await query.edit_message_text(
                text=f"✅ Item '{item_name}' added as new and saved for future recognition."
            )

            # Добавляем паузу для чтения сообщения
            await asyncio.sleep(1.5)

            # Находим следующий неопознанный товар
            next_unmatched = None
            for i, line in enumerate(matched_data.get("lines", [])):
                if line.get("product_id") is None:
                    next_unmatched = i
                    break

            if next_unmatched is not None:
                # Переходим к следующему неопознанному товару
                user_data[user_id]["current_edit_index"] = next_unmatched
                await display_item_edit_options(query, user_id, next_unmatched)
                return EDIT_ITEM
            else:
                # Все товары обработаны, переходим к предварительному просмотру
                await query.edit_message_text(
                    text="✅ All items processed!\n\n" "Ready to review final invoice?",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "Review Final Invoice",
                                    callback_data="final_preview",
                                )
                            ],
                            [InlineKeyboardButton("Cancel", callback_data="cancel_process")],
                        ]
                    ),
                )
                return CONFIRMATION

        # Возврат к редактированию товара
        elif query.data.startswith("back_to_edit:"):
            item_index = int(query.data.split(":")[1])
            await display_item_edit_options(query, user_id, item_index)
            return EDIT_ITEM

        # Переход к следующему неопознанному товару
        elif query.data.startswith("next_unmatched:"):
            next_index = int(query.data.split(":")[1])
            user_data[user_id]["current_edit_index"] = next_index
            await display_item_edit_options(query, user_id, next_index)
            return EDIT_ITEM

        # Настройка конвертации единиц измерения
        elif query.data.startswith("set_conversion:"):
            item_index = int(query.data.split(":")[1])
            item_name = matched_data["lines"][item_index].get("name", "")
            current_unit = matched_data["lines"][item_index].get("unit", "")

            await query.edit_message_text(
                text=f"Setting unit conversion for '{item_name}'.\n\n"
                f"Current unit: {current_unit}\n\n"
                "Please enter the target unit (e.g., kg, l, pcs):"
            )

            # Сохраняем данные для обработчика конверсии
            context.user_data["setting_conversion"] = {
                "item_index": item_index,
                "product_name": item_name,
                "source_unit": current_unit,
                "step": "target_unit",
            }

            return SET_CONVERSION

        # Возврат к предыдущему шагу редактирования
        elif query.data == "previous_step":
            # Проверяем наличие истории редактирования
            if not user_data[user_id].get("edit_history"):
                await query.edit_message_text(
                    text="Cannot go back: no edit history found.",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "Continue Editing",
                                    callback_data=f"back_to_edit:{current_index}",
                                )
                            ]
                        ]
                    ),
                )
                return EDIT_ITEM

            # Восстанавливаем предыдущее состояние
            previous_state = user_data[user_id]["edit_history"].pop()
            user_data[user_id]["matched_data"] = previous_state

            # Отображаем информацию о текущем товаре
            await display_item_edit_options(query, user_id, current_index)
            return EDIT_ITEM

        # Возврат к выбору товара
        elif query.data == "back_to_selection":
            await display_item_selection(query, user_id)
            return SELECT_EDIT_ITEM

        # Возврат к основному экрану
        elif query.data == "back_to_main":
            message_text = format_invoice_data(user_data[user_id])

            # Создаем клавиатуру для действий
            keyboard = []

            # Проверяем наличие неопознанных товаров
            unmatched_items = [
                item for item in matched_data.get("lines", []) if item.get("product_id") is None
            ]

            if unmatched_items:
                keyboard.append(
                    [InlineKeyboardButton("Fix Unrecognized Items", callback_data="edit_unmatched")]
                )

            keyboard.append(
                [InlineKeyboardButton("Review & Edit Items", callback_data="select_edit_item")]
            )

            if not unmatched_items:
                keyboard.append(
                    [InlineKeyboardButton("Confirm & Preview Final", callback_data="final_preview")]
                )

            keyboard.append([InlineKeyboardButton("Cancel", callback_data="cancel_process")])

            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(text=message_text, reply_markup=reply_markup)
            return CONFIRMATION

        # Отмена операции
        elif query.data == "cancel_process":
            if user_id in user_data:
                del user_data[user_id]

            await query.edit_message_text(text="Operation canceled. Send a new invoice photo.")
            return WAIT_PHOTO

        return EDIT_ITEM

    except Exception as e:
        error_msg = f"Error in handle_item_edit: {e}"
        log_error(error_msg, exc_info=True)

        try:
            await query.edit_message_text(
                text="❌ An error occurred. Please try again or start over with /cancel."
            )
        except Exception as inner_e:
            log_error(f"Error sending error message: {inner_e}", exc_info=True)

        return WAIT_PHOTO


async def handle_manual_item_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик ручного ввода названия товара

    Args:
        update: Входящее обновление
        context: Контекст

    Returns:
        int: Следующее состояние диалога
    """
    try:
        user_id = update.effective_user.id

        if user_id not in user_data:
            await update.message.reply_text("Error: Invoice data not found.")
            return WAIT_PHOTO

        if "awaiting_item_name" not in context.user_data:
            await update.message.reply_text("Error: No item being edited.")
            return WAIT_PHOTO

        # Получаем введенное пользователем название товара
        entered_name = update.message.text.strip()
        item_index = context.user_data["awaiting_item_name"]["item_index"]
        original_name = context.user_data["awaiting_item_name"]["original_name"]

        # Сохраняем текущее состояние для возможности возврата
        if "edit_history" not in user_data[user_id]:
            user_data[user_id]["edit_history"] = []

        # Клонируем текущее состояние
        current_state = json.loads(json.dumps(user_data[user_id]["matched_data"]))
        user_data[user_id]["edit_history"].append(current_state)

        # Проверяем, существует ли товар в базе
        exists, product_id = await check_product_exists(entered_name)

        if exists and product_id:
            # Товар существует, используем найденный ID
            user_data[user_id]["matched_data"]["lines"][item_index]["product_id"] = product_id
            user_data[user_id]["matched_data"]["lines"][item_index]["match_score"] = 1.0
            user_data[user_id]["matched_data"]["lines"][item_index]["manual_name"] = entered_name

            # Сохраняем это сопоставление для будущего использования
            save_learned_mapping(original_name, product_id, entered_name)

            await update.message.reply_text(
                f"✅ Found product '{entered_name}' in database!\n\n"
                f"Item '{original_name}' successfully matched and saved for future recognition."
            )
        else:
            # Запрашиваем подтверждение для добавления нового товара
            keyboard = [
                [
                    InlineKeyboardButton(
                        "Yes, add as new",
                        callback_data=f"confirm_manual_new:{item_index}:{entered_name}",
                    ),
                    InlineKeyboardButton(
                        "No, try again", callback_data=f"retry_manual:{item_index}"
                    ),
                ]
            ]

            await update.message.reply_text(
                f"❓ Product '{entered_name}' not found in database.\n\n"
                "Would you like to add it as a new product?",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

            # Сохраняем введенное название
            context.user_data["awaiting_item_name"]["entered_name"] = entered_name

            return ADD_NEW_ITEM

        # Очищаем временные данные
        del context.user_data["awaiting_item_name"]

        # Переходим к следующему неопознанному товару или возвращаемся к выбору
        matched_data = user_data[user_id]["matched_data"]
        next_unmatched = None

        for i, line in enumerate(matched_data.get("lines", [])):
            if line.get("product_id") is None:
                next_unmatched = i
                break

        if next_unmatched is not None:
            # Обновляем индекс текущего редактируемого товара
            user_data[user_id]["current_edit_index"] = next_unmatched

            # Создаем клавиатуру для следующего товара
            keyboard = [
                [
                    InlineKeyboardButton(
                        "Enter correct item",
                        callback_data=f"manual_match:{next_unmatched}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "Add as new item", callback_data=f"add_new:{next_unmatched}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "Set unit conversion",
                        callback_data=f"set_conversion:{next_unmatched}",
                    )
                ],
            ]

            # Добавляем кнопку возврата к предыдущему шагу
            if user_data[user_id].get("edit_history"):
                keyboard.append(
                    [InlineKeyboardButton("Previous Step", callback_data="previous_step")]
                )

            # Добавляем кнопки навигации
            keyboard.append(
                [
                    InlineKeyboardButton("Back to Main", callback_data="back_to_main"),
                    InlineKeyboardButton("Cancel", callback_data="cancel_process"),
                ]
            )

            # Отображаем информацию о товаре
            line = matched_data["lines"][next_unmatched]
            line_num = line.get("line", next_unmatched + 1)
            name = line.get("name", "Unknown item")
            qty = line.get("qty", 0)
            unit = line.get("unit", "")
            price = line.get("price", 0)

            # Считаем позицию среди неопознанных товаров
            unmatched_indices = [
                i
                for i, l in enumerate(matched_data.get("lines", []))
                if l.get("product_id") is None
            ]
            current_position = unmatched_indices.index(next_unmatched) + 1
            total_unmatched = len(unmatched_indices)

            message_text = (
                f"Editing item {current_position} of {total_unmatched}:\n\n"
                f"Line: {line_num}\n"
                f"Name: {name}\n"
                f"Quantity: {qty} {unit}\n"
                f"Price: {price} IDR\n\n"
                "Select action:"
            )

            await update.message.reply_text(
                text=message_text, reply_markup=InlineKeyboardMarkup(keyboard)
            )

            return EDIT_ITEM
        else:
            # Все товары обработаны, переходим к предварительному просмотру
            await update.message.reply_text(
                "✅ All items processed!\n\n" "Ready to review final invoice?",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "Review Final Invoice", callback_data="final_preview"
                            )
                        ],
                        [InlineKeyboardButton("Cancel", callback_data="cancel_process")],
                    ]
                ),
            )

            return CONFIRMATION

    except Exception as e:
        error_msg = f"Error in handle_manual_item_entry: {e}"
        log_error(error_msg, exc_info=True)
        await update.message.reply_text(
            "❌ An error occurred. Please try again or start over with /cancel."
        )
        return WAIT_PHOTO


async def handle_manual_entry_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик колбэков при ручном вводе товара

    Args:
        update: Входящее обновление
        context: Контекст

    Returns:
        int: Следующее состояние диалога
    """
    try:
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id

        if user_id not in user_data:
            await query.edit_message_text("Error: Invoice data not found.")
            return WAIT_PHOTO

        # Подтверждение добавления нового товара на основе ручного ввода
        if query.data.startswith("confirm_manual_new:"):
            parts = query.data.split(":")
            item_index = int(parts[1])

            # Если в callback_data нет имени, берем из context.user_data
            if len(parts) > 2:
                entered_name = parts[2]
            else:
                if (
                    "awaiting_item_name" not in context.user_data
                    or "entered_name" not in context.user_data["awaiting_item_name"]
                ):
                    await query.edit_message_text("Error: Item name data not found.")
                    return EDIT_ITEM
                entered_name = context.user_data["awaiting_item_name"].get("entered_name", "")

            original_name = context.user_data["awaiting_item_name"]["original_name"]

            # Генерируем новый ID товара
            new_product_id = (
                f"manual_new_{item_index}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            )
            user_data[user_id]["matched_data"]["lines"][item_index]["product_id"] = new_product_id
            user_data[user_id]["matched_data"]["lines"][item_index]["match_score"] = 1.0
            user_data[user_id]["matched_data"]["lines"][item_index]["manual_name"] = entered_name

            # Сохраняем сопоставление
            save_learned_mapping(original_name, new_product_id, entered_name)

            await query.edit_message_text(
                f"✅ Item '{entered_name}' added as new and saved for future recognition."
            )

            # Очищаем временные данные
            if "awaiting_item_name" in context.user_data:
                del context.user_data["awaiting_item_name"]

            # Добавляем паузу для чтения сообщения
            await asyncio.sleep(1.5)

            # Находим следующий неопознанный товар
            matched_data = user_data[user_id]["matched_data"]
            next_unmatched = None

            for i, line in enumerate(matched_data.get("lines", [])):
                if line.get("product_id") is None:
                    next_unmatched = i
                    break

            if next_unmatched is not None:
                # Переходим к следующему неопознанному товару
                user_data[user_id]["current_edit_index"] = next_unmatched
                await display_item_edit_options(query, user_id, next_unmatched)
                return EDIT_ITEM
            else:
                # Все товары обработаны, переходим к предварительному просмотру
                await query.edit_message_text(
                    text="✅ All items processed!\n\n" "Ready to review final invoice?",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "Review Final Invoice",
                                    callback_data="final_preview",
                                )
                            ],
                            [InlineKeyboardButton("Cancel", callback_data="cancel_process")],
                        ]
                    ),
                )
                return CONFIRMATION

        # Повторная попытка ввода названия товара
        elif query.data.startswith("retry_manual:"):
            item_index = int(query.data.split(":")[1])
            item_name = user_data[user_id]["matched_data"]["lines"][item_index].get("name", "")

            await query.edit_message_text(
                text=f"Please try entering a different name for '{item_name}'.\n\n"
                "Make sure to type the exact name as it appears in your product database."
            )

            # Сохраняем данные для обработчика текстовых сообщений
            if "awaiting_item_name" not in context.user_data:
                context.user_data["awaiting_item_name"] = {}

            context.user_data["awaiting_item_name"]["item_index"] = item_index
            context.user_data["awaiting_item_name"]["original_name"] = item_name

            return ADD_NEW_ITEM

        # Обработка других колбэков при ручном вводе товара
        elif query.data.startswith("back_to_edit:"):
            item_index = int(query.data.split(":")[1])
            await display_item_edit_options(query, user_id, item_index)
            return EDIT_ITEM

        elif query.data == "cancel_process":
            if user_id in user_data:
                del user_data[user_id]

            if "awaiting_item_name" in context.user_data:
                del context.user_data["awaiting_item_name"]

            await query.edit_message_text(text="Operation canceled. Send a new invoice photo.")
            return WAIT_PHOTO

        return ADD_NEW_ITEM

    except Exception as e:
        error_msg = f"Error in handle_manual_entry_callback: {e}"
        log_error(error_msg, exc_info=True)

        try:
            await query.edit_message_text(
                text="❌ An error occurred. Please try again or start over with /cancel."
            )
        except Exception:
            pass

        return WAIT_PHOTO


async def handle_conversion_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик ввода данных для конвертации единиц измерения

    Args:
        update: Входящее обновление
        context: Контекст

    Returns:
        int: Следующее состояние диалога
    """
    try:
        user_id = update.effective_user.id

        if user_id not in user_data:
            await update.message.reply_text("Error: Invoice data not found.")
            return WAIT_PHOTO

        if "setting_conversion" not in context.user_data:
            await update.message.reply_text("Error: No conversion being set.")
            return WAIT_PHOTO

        # Получаем текст от пользователя
        input_text = update.message.text.strip()

        # Получаем текущий шаг настройки конвертации
        conversion_data = context.user_data["setting_conversion"]
        current_step = conversion_data.get("step")

        if current_step == "target_unit":
            # Пользователь ввел целевую единицу измерения
            target_unit = input_text.lower()

            # Сохраняем целевую единицу и переходим к запросу коэффициента
            conversion_data["target_unit"] = target_unit
            conversion_data["step"] = "conversion_factor"

            await update.message.reply_text(
                text=f"Setting unit conversion from {conversion_data['source_unit']} to {target_unit}.\n\n"
                f"Please enter the conversion factor (e.g., 0.5 means 1 {conversion_data['source_unit']} = 0.5 {target_unit}):"
            )

            return SET_CONVERSION

        elif current_step == "conversion_factor":
            # Пользователь ввел коэффициент конвертации
            try:
                conversion_factor = float(input_text.replace(",", "."))

                # Получаем данные о товаре
                item_index = conversion_data["item_index"]
                product_name = conversion_data["product_name"]
                source_unit = conversion_data["source_unit"]
                target_unit = conversion_data["target_unit"]

                # Получаем ID товара
                matched_data = user_data[user_id]["matched_data"]
                product_id = matched_data["lines"][item_index].get("product_id")

                if not product_id:
                    # Если товар не распознан, генерируем временный ID
                    product_id = (
                        f"temp_{item_index}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
                    )
                    matched_data["lines"][item_index]["product_id"] = product_id

                # Сохраняем конвертацию в базу данных
                save_unit_conversion(
                    product_id,
                    product_name,
                    source_unit,
                    target_unit,
                    conversion_factor,
                )

                # Применяем конвертацию к текущему товару
                qty = matched_data["lines"][item_index].get("qty", 0)
                matched_data["lines"][item_index]["original_qty"] = qty
                matched_data["lines"][item_index]["original_unit"] = source_unit
                matched_data["lines"][item_index]["qty"] = qty * conversion_factor
                matched_data["lines"][item_index]["unit"] = target_unit
                matched_data["lines"][item_index]["conversion_applied"] = True

                # Добавляем информацию о конвертации
                if "conversions_applied" not in user_data[user_id]:
                    user_data[user_id]["conversions_applied"] = []

                user_data[user_id]["conversions_applied"].append(
                    {
                        "line_index": item_index,
                        "product_name": product_name,
                        "product_id": product_id,
                        "original_qty": qty,
                        "original_unit": source_unit,
                        "converted_qty": qty * conversion_factor,
                        "converted_unit": target_unit,
                        "conversion_factor": conversion_factor,
                    }
                )

                # Отображаем успешное завершение
                await update.message.reply_text(
                    "✅ Unit conversion set successfully!\n\n"
                    f"1 {source_unit} = {conversion_factor} {target_unit}\n\n"
                    f"This conversion will be automatically applied to all '{product_name}' items in future invoices."
                )

                # Очищаем временные данные
                del context.user_data["setting_conversion"]

                # Создаем клавиатуру для дальнейших действий
                keyboard = []

                # Проверяем наличие неопознанных товаров
                unmatched_items = [
                    i
                    for i, line in enumerate(matched_data.get("lines", []))
                    if line.get("product_id") is None
                ]

                if unmatched_items:
                    keyboard.append(
                        [
                            InlineKeyboardButton(
                                "Continue with unrecognized items",
                                callback_data=f"next_unmatched:{unmatched_items[0]}",
                            )
                        ]
                    )

                keyboard.append(
                    [
                        InlineKeyboardButton("Review all items", callback_data="select_edit_item"),
                        InlineKeyboardButton("Back to Main", callback_data="back_to_main"),
                    ]
                )

                keyboard.append([InlineKeyboardButton("Cancel", callback_data="cancel_process")])

                await update.message.reply_text(
                    "What would you like to do next?",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )

                return EDIT_ITEM

            except ValueError:
                # Неверный формат числа
                await update.message.reply_text(
                    "Please enter a valid number for the conversion factor (e.g., 0.5, 2, 1.25)."
                )

                return SET_CONVERSION

        # Если шаг не определен, возвращаемся к редактированию
        return EDIT_ITEM

    except Exception as e:
        error_msg = f"Error in handle_conversion_entry: {e}"
        log_error(error_msg, exc_info=True)
        await update.message.reply_text(
            "❌ An error occurred. Please try again or start over with /cancel."
        )
        return WAIT_PHOTO


async def handle_conversion_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик колбэков при настройке конвертации единиц измерения

    Args:
        update: Входящее обновление
        context: Контекст

    Returns:
        int: Следующее состояние диалога
    """
    try:
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id

        if user_id not in user_data:
            await query.edit_message_text("Error: Invoice data not found.")
            return WAIT_PHOTO

        if query.data == "cancel_process":
            if user_id in user_data:
                del user_data[user_id]

            if "setting_conversion" in context.user_data:
                del context.user_data["setting_conversion"]

            await query.edit_message_text(text="Operation canceled. Send a new invoice photo.")
            return WAIT_PHOTO

        elif query.data == "back_to_edit" and "setting_conversion" in context.user_data:
            # Возвращаемся к редактированию товара
            item_index = context.user_data["setting_conversion"].get("item_index")

            if item_index is not None:
                del context.user_data["setting_conversion"]
                await display_item_edit_options(query, user_id, item_index)
                return EDIT_ITEM

        # В остальных случаях продолжаем настройку конвертации
        return SET_CONVERSION

    except Exception as e:
        error_msg = f"Error in handle_conversion_callback: {e}"
        log_error(error_msg, exc_info=True)

        try:
            await query.edit_message_text(
                text="❌ An error occurred. Please try again or start over with /cancel."
            )
        except Exception:
            pass

        return WAIT_PHOTO
