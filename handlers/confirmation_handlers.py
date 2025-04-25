"""
Обработчики для подтверждения действий в Telegram-боте.
"""

import logging
import math
from typing import List, Dict

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import CONFIRMATION, FINAL_CONFIRMATION, WAIT_PHOTO, SET_BUYER, SELECT_SUPPLIER
from services.syrve_service import send_invoice_to_syrve
from utils.configuration import Config
from utils.invoice_processing import format_invoice_for_display, load_suppliers

# Настройка логирования
logger = logging.getLogger(__name__)

# Количество поставщиков на одной странице выбора
SUPPLIERS_PER_PAGE = 10


async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик подтверждения данных.
    
    Args:
        update: Объект Update от Telegram
        context: Контекст бота
        
    Returns:
        int: Следующее состояние диалога
    """
    query = update.callback_query
    user = query.from_user
    
    # Отвечаем на колбэк, чтобы убрать индикатор загрузки
    await query.answer()
    
    # Получаем данные колбэка
    callback_data = query.data
    
    if callback_data == "confirm_action":
        # Получаем данные для подтверждения
        if "confirm_data" not in context.user_data:
            logger.warning(f"No confirmation data for user {user.id}")
            await query.edit_message_text(
                "❌ Error: no confirmation data found."
            )
            return WAIT_PHOTO
        
        confirm_data = context.user_data["confirm_data"]
        action_type = confirm_data.get("type", "unknown")
        
        if action_type == "invoice":
            invoice_data = confirm_data.get("data")
            
            # Получаем настройки Syrve
            config = Config()
            
            # Отправляем накладную в Syrve
            try:
                invoice_id = await send_invoice_to_syrve(
                    invoice_data,
                    config.SYRVE_LOGIN,
                    config.SYRVE_PASSWORD,
                    config.SYRVE_BASE_URL
                )
                
                if invoice_id:
                    await query.edit_message_text(
                        f"✅ Invoice successfully sent to Syrve!\n\nID: {invoice_id}"
                    )
                    logger.info(f"User {user.id} successfully sent invoice to Syrve")
                else:
                    await query.edit_message_text(
                        "❌ Failed to send invoice to Syrve. Please try again later."
                    )
                    logger.error(f"Failed to send invoice to Syrve for user {user.id}")
            except Exception as e:
                logger.error(f"Error sending invoice to Syrve: {str(e)}", exc_info=True)
                await query.edit_message_text(
                    "❌ Error occurred while sending invoice to Syrve."
                )
            
            return WAIT_PHOTO
        else:
            logger.warning(f"Unknown action type: {action_type}")
            await query.edit_message_text(
                f"❌ Unknown action type: {action_type}"
            )
            return WAIT_PHOTO
    
    elif callback_data == "reject_action":
        await query.edit_message_text(
            "❌ Action canceled by user."
        )
        logger.info(f"User {user.id} rejected action")
        return WAIT_PHOTO
    
    elif callback_data == "final_preview":
        # Здесь будет логика для перехода к финальному предпросмотру
        await query.edit_message_text(
            "Preparing final preview...",
        )
        # Очищаем предыдущие данные предпросмотра
        context.user_data.pop("preview_data", None)
        return FINAL_CONFIRMATION
    
    elif callback_data == "select_supplier":
        # Обработка запроса на выбор поставщика
        await handle_supplier_selection(update, context, page=0)
        return SELECT_SUPPLIER
    
    elif callback_data.startswith("choose_supplier_"):
        # Обработка выбора конкретного поставщика
        supplier_id = callback_data.replace("choose_supplier_", "")
        await handle_supplier_choice(update, context, supplier_id)
        return CONFIRMATION
    
    elif callback_data.startswith("supplier_page_"):
        # Обработка переключения страницы в списке поставщиков
        page = int(callback_data.replace("supplier_page_", ""))
        await handle_supplier_selection(update, context, page)
        return SELECT_SUPPLIER
    
    elif callback_data == "set_buyer":
        # Обработка запроса на ввод покупателя
        await ask_buyer_input(update, context)
        return SET_BUYER
    
    else:
        logger.warning(f"Unknown callback data in handle_confirmation: {callback_data}")
        return CONFIRMATION


async def handle_supplier_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0) -> None:
    """
    Показывает инлайн-меню с поставщиками для выбора.
    
    Args:
        update: Объект Update от Telegram
        context: Контекст бота
        page: Номер страницы для отображения
    """
    query = update.callback_query
    
    # Загружаем список поставщиков
    suppliers = load_suppliers()
    
    if not suppliers:
        await query.edit_message_text(
            "❌ Error: suppliers list is empty. Please contact support."
        )
        return
    
    # Рассчитываем общее количество страниц
    total_pages = math.ceil(min(50, len(suppliers)) / SUPPLIERS_PER_PAGE)
    
    # Защита от выхода за пределы
    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1
    
    # Отбираем поставщиков для текущей страницы
    start_idx = page * SUPPLIERS_PER_PAGE
    end_idx = min(start_idx + SUPPLIERS_PER_PAGE, min(50, len(suppliers)))
    page_suppliers = suppliers[start_idx:end_idx]
    
    # Создаем кнопки
    keyboard = []
    
    # Добавляем кнопки для поставщиков
    for supplier in page_suppliers:
        supplier_id = supplier.get("id", "")
        supplier_name = supplier.get("name", "")
        keyboard.append([
            InlineKeyboardButton(supplier_name, callback_data=f"choose_supplier_{supplier_id}")
        ])
    
    # Добавляем навигацию по страницам
    navigation = []
    
    if page > 0:
        navigation.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"supplier_page_{page-1}"))
    
    if page < total_pages - 1:
        navigation.append(InlineKeyboardButton("Next ➡️", callback_data=f"supplier_page_{page+1}"))
    
    if navigation:
        keyboard.append(navigation)
    
    # Добавляем кнопку отмены
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="back_to_edit")])
    
    # Отображаем меню
    await query.edit_message_text(
        f"Select supplier (page {page+1}/{total_pages}):",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_supplier_choice(update: Update, context: ContextTypes.DEFAULT_TYPE, supplier_id: str) -> None:
    """
    Обрабатывает выбор поставщика пользователем.
    
    Args:
        update: Объект Update от Telegram
        context: Контекст бота
        supplier_id: ID выбранного поставщика
    """
    query = update.callback_query
    
    # Загружаем список поставщиков для получения имени
    suppliers = load_suppliers()
    supplier_name = None
    
    for supplier in suppliers:
        if supplier.get("id") == supplier_id:
            supplier_name = supplier.get("name", "Unknown supplier")
            break
    
    if not supplier_name:
        logger.warning(f"Supplier with ID {supplier_id} not found")
        supplier_name = "Unknown supplier"
    
    # Обновляем данные накладной
    invoice_data = context.user_data.get("invoice", {})
    invoice_data["vendor_id"] = supplier_id
    invoice_data["vendor_name"] = supplier_name
    invoice_data["vendor_status"] = "matched"
    invoice_data["vendor_confidence"] = 1.0
    
    # Перерисовываем сообщение с обновленными данными
    formatted_message = format_invoice_for_display(invoice_data)
    
    # Обновляем клавиатуру
    keyboard = []
    
    # Проверяем, есть ли buyer
    buyer_found = invoice_data.get("buyer_found", False)
    if not buyer_found:
        keyboard.append([
            InlineKeyboardButton("🖊️ Set buyer", callback_data="set_buyer")
        ])
    
    # Добавляем кнопки для неопознанных или невалидных товаров
    unmatched_items = [
        item for item in invoice_data.get("items", [])
        if item.get("match_status") == "unmatched" or not item.get("is_valid", True)
    ]
    
    fix_buttons = []
    for i, item in enumerate(unmatched_items):
        item_index = invoice_data["items"].index(item)
        fix_buttons.append(
            InlineKeyboardButton(f"Fix_{item_index+1}", callback_data=f"fix_item_{item_index}")
        )
        
        # Создаем ряды по 3 кнопки
        if len(fix_buttons) == 3 or i == len(unmatched_items) - 1:
            keyboard.append(fix_buttons)
            fix_buttons = []
    
    # Добавляем кнопку подтверждения, если все в порядке
    unmatched_count = invoice_data.get("unmatched_count", 0)
    if unmatched_count == 0 and buyer_found:
        keyboard.append([
            InlineKeyboardButton("✅ Confirm & send to Syrve", callback_data="send_to_syrve")
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Сохраняем обновленные данные и перерисовываем сообщение
    context.user_data["invoice"] = invoice_data
    
    await query.edit_message_text(
        formatted_message + "\n\n<i>Supplier updated. Review and confirm when ready.</i>",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )


async def ask_buyer_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Запрашивает у пользователя ввод названия покупателя.
    
    Args:
        update: Объект Update от Telegram
        context: Контекст бота
    """
    query = update.callback_query
    
    await query.edit_message_text(
        "Please enter the buyer name:\n\n"
        "<i>Type any text to set as the buyer name.</i>",
        parse_mode="HTML"
    )


async def handle_buyer_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает ввод названия покупателя от пользователя.
    
    Args:
        update: Объект Update от Telegram
        context: Контекст бота
        
    Returns:
        int: Следующее состояние диалога
    """
    try:
        # Получаем введенный текст
        buyer_name = update.message.text.strip()
        
        if not buyer_name:
            await update.message.reply_text(
                "❌ Buyer name cannot be empty. Please try again."
            )
            return SET_BUYER
        
        # Обновляем данные накладной
        invoice_data = context.user_data.get("invoice", {})
        invoice_data["buyer_name"] = buyer_name
        invoice_data["buyer_found"] = True
        invoice_data["buyer_status"] = "matched"
        invoice_data["buyer_confidence"] = 1.0
        
        # Перерисовываем сообщение с обновленными данными
        formatted_message = format_invoice_for_display(invoice_data)
        
        # Обновляем клавиатуру
        keyboard = []
        
        # Проверяем наличие поставщика
        supplier_id = invoice_data.get("vendor_id")
        if not supplier_id:
            keyboard.append([
                InlineKeyboardButton("🖊️ Select supplier", callback_data="select_supplier")
            ])
        
        # Добавляем кнопки для неопознанных или невалидных товаров
        unmatched_items = [
            item for item in invoice_data.get("items", [])
            if item.get("match_status") == "unmatched" or not item.get("is_valid", True)
        ]
        
        fix_buttons = []
        for i, item in enumerate(unmatched_items):
            item_index = invoice_data["items"].index(item)
            fix_buttons.append(
                InlineKeyboardButton(f"Fix_{item_index+1}", callback_data=f"fix_item_{item_index}")
            )
            
            # Создаем ряды по 3 кнопки
            if len(fix_buttons) == 3 or i == len(unmatched_items) - 1:
                keyboard.append(fix_buttons)
                fix_buttons = []
        
        # Добавляем кнопку подтверждения, если все в порядке
        unmatched_count = invoice_data.get("unmatched_count", 0)
        if unmatched_count == 0 and supplier_id:
            keyboard.append([
                InlineKeyboardButton("✅ Confirm & send to Syrve", callback_data="send_to_syrve")
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Сохраняем обновленные данные и отправляем сообщение
        context.user_data["invoice"] = invoice_data
        
        await update.message.reply_text(
            formatted_message + "\n\n<i>Buyer updated. Review and confirm when ready.</i>",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        
        return CONFIRMATION
    
    except Exception as e:
        logger.error(f"Error handling buyer input: {str(e)}", exc_info=True)
        
        await update.message.reply_text(
            "❌ An error occurred while updating the buyer. Please try again."
        )
        
        return CONFIRMATION


async def handle_final_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик финального подтверждения перед отправкой.
    
    Args:
        update: Объект Update от Telegram
        context: Контекст бота
        
    Returns:
        int: Следующее состояние диалога
    """
    query = update.callback_query
    user = query.from_user
    
    # Отвечаем на колбэк, чтобы убрать индикатор загрузки
    await query.answer()
    
    # Получаем данные колбэка
    callback_data = query.data
    
    if callback_data == "send_to_syrve":
        # Получаем данные накладной
        if "invoice" not in context.user_data:
            logger.warning(f"No invoice data for user {user.id}")
            await query.edit_message_text(
                "❌ Error: invoice data not found."
            )
            return WAIT_PHOTO
        
        invoice_data = context.user_data["invoice"]
        
        # Получаем настройки Syrve
        config = Config()
        
        # Отправляем накладную в Syrve
        try:
            invoice_id = await send_invoice_to_syrve(
                invoice_data,
                config.SYRVE_LOGIN,
                config.SYRVE_PASSWORD,
                config.SYRVE_BASE_URL
            )
            
            if invoice_id:
                await query.edit_message_text(
                    "Invoice sent to Syrve ✔️"
                )
                logger.info(f"User {user.id} successfully sent invoice to Syrve")
            else:
                await query.edit_message_text(
                    "❌ Failed to send invoice to Syrve. Please try again later."
                )
                logger.error(f"Failed to send invoice to Syrve for user {user.id}")
        except Exception as e:
            logger.error(f"Error sending invoice to Syrve: {str(e)}", exc_info=True)
            await query.edit_message_text(
                "❌ Error occurred while sending invoice to Syrve."
            )
        
        # Очищаем данные пользователя
        context.user_data.clear()
        return WAIT_PHOTO
    
    elif callback_data == "edit_more":
        # Возвращаемся к редактированию
        keyboard = [
            [InlineKeyboardButton("Edit items", callback_data="select_edit_item")],
            [InlineKeyboardButton("Back to preview", callback_data="final_preview")],
            [InlineKeyboardButton("Cancel", callback_data="cancel_process")]
        ]
        
        await query.edit_message_text(
            "Select action:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return CONFIRMATION
    
    elif callback_data == "cancel_process":
        await query.edit_message_text(
            "❌ Invoice sending process canceled."
        )
        logger.info(f"User {user.id} canceled invoice process")
        
        # Очищаем данные пользователя
        context.user_data.clear()
        return WAIT_PHOTO
    
    else:
        logger.warning(f"Unknown callback data in handle_final_confirmation: {callback_data}")
        return FINAL_CONFIRMATION
