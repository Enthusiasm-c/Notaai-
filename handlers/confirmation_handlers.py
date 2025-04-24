"""
Обработчики для подтверждения действий в Telegram-боте.
"""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import CONFIRMATION, FINAL_CONFIRMATION, WAIT_PHOTO
from services.syrve_service import send_invoice_to_syrve
from utils.configuration import Config

# Настройка логирования
logger = logging.getLogger(__name__)


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
                "❌ Ошибка: данные для подтверждения не найдены."
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
                        f"✅ Накладная успешно отправлена в Syrve!\n\nID: {invoice_id}"
                    )
                    logger.info(f"User {user.id} successfully sent invoice to Syrve")
                else:
                    await query.edit_message_text(
                        "❌ Не удалось отправить накладную в Syrve. Попробуйте позже."
                    )
                    logger.error(f"Failed to send invoice to Syrve for user {user.id}")
            except Exception as e:
                logger.error(f"Error sending invoice to Syrve: {str(e)}", exc_info=True)
                await query.edit_message_text(
                    "❌ Произошла ошибка при отправке накладной в Syrve."
                )
            
            return WAIT_PHOTO
        else:
            logger.warning(f"Unknown action type: {action_type}")
            await query.edit_message_text(
                f"❌ Неизвестный тип действия: {action_type}"
            )
            return WAIT_PHOTO
    
    elif callback_data == "reject_action":
        await query.edit_message_text(
            "❌ Действие отменено пользователем."
        )
        logger.info(f"User {user.id} rejected action")
        return WAIT_PHOTO
    
    elif callback_data == "final_preview":
        # Здесь будет логика для перехода к финальному предпросмотру
        await query.edit_message_text(
            "Подготовка финального предпросмотра...",
        )
        # Очищаем предыдущие данные предпросмотра
        context.user_data.pop("preview_data", None)
        return FINAL_CONFIRMATION
    
    else:
        logger.warning(f"Unknown callback data in handle_confirmation: {callback_data}")
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
                "❌ Ошибка: данные накладной не найдены."
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
                    f"✅ Накладная успешно отправлена в Syrve!\n\nID: {invoice_id}"
                )
                logger.info(f"User {user.id} successfully sent invoice to Syrve")
            else:
                await query.edit_message_text(
                    "❌ Не удалось отправить накладную в Syrve. Попробуйте позже."
                )
                logger.error(f"Failed to send invoice to Syrve for user {user.id}")
        except Exception as e:
            logger.error(f"Error sending invoice to Syrve: {str(e)}", exc_info=True)
            await query.edit_message_text(
                "❌ Произошла ошибка при отправке накладной в Syrve."
            )
        
        # Очищаем данные пользователя
        context.user_data.clear()
        return WAIT_PHOTO
    
    elif callback_data == "edit_more":
        # Возвращаемся к редактированию
        keyboard = [
            [InlineKeyboardButton("Редактировать товары", callback_data="select_edit_item")],
            [InlineKeyboardButton("Назад к предпросмотру", callback_data="final_preview")],
            [InlineKeyboardButton("Отмена", callback_data="cancel_process")]
        ]
        
        await query.edit_message_text(
            "Выберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return CONFIRMATION
    
    elif callback_data == "cancel_process":
        await query.edit_message_text(
            "❌ Процесс отправки накладной отменен."
        )
        logger.info(f"User {user.id} canceled invoice process")
        
        # Очищаем данные пользователя
        context.user_data.clear()
        return WAIT_PHOTO
    
    else:
        logger.warning(f"Unknown callback data in handle_final_confirmation: {callback_data}")
        return FINAL_CONFIRMATION
