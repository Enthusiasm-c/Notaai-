import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import WAIT_PHOTO, user_data
from utils.error_handling import log_error

# Получаем логгер
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик команды /start

    Args:
        update: Входящее обновление
        context: Контекст

    Returns:
        int: Следующее состояние диалога
    """
    try:
        await update.message.reply_text(
            "👋 Hello! I'm Nota AI - your intelligent invoice processing assistant.\n\n"
            "I can help you:\n"
            "• Extract data from invoice photos\n"
            "• Match items with your product database\n"
            "• Convert units of measurement automatically\n"
            "• Send structured data to Syrve\n\n"
            "Simply send me a photo of an invoice to get started!"
        )
        return WAIT_PHOTO
    except Exception as e:
        log_error(f"Error in start command: {e}", exc_info=True)
        await update.message.reply_text("An error occurred. Please try again.")
        return WAIT_PHOTO


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик команды /help

    Args:
        update: Входящее обновление
        context: Контекст

    Returns:
        int: Следующее состояние диалога
    """
    try:
        await update.message.reply_text(
            "📋 Nota AI Help Guide:\n\n"
            "Basic Commands:\n"
            "/start - Start working with the bot\n"
            "/help - Show this message\n"
            "/cancel - Cancel the current operation\n\n"
            "How to use Nota AI:\n"
            "1. 📸 Send a photo of an invoice\n"
            "2. 🔍 I'll process the image and extract data\n"
            "3. ✏️ Fix any unrecognized items\n"
            "4. 🔄 Set unit conversions if needed\n"
            "5. 📋 Review the final data before sending\n"
            "6. ✅ Confirm to send data to Syrve\n\n"
            "Advanced Features:\n"
            "• You can edit any item before final confirmation\n"
            "• You can go back to previous steps if needed\n"
            "• Unit conversions are remembered for future invoices"
        )
        return WAIT_PHOTO
    except Exception as e:
        log_error(f"Error in help command: {e}", exc_info=True)
        await update.message.reply_text("An error occurred. Please try again.")
        return WAIT_PHOTO


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик команды /cancel

    Args:
        update: Входящее обновление
        context: Контекст

    Returns:
        int: Следующее состояние диалога
    """
    try:
        user_id = update.effective_user.id
        if user_id in user_data:
            del user_data[user_id]

        await update.message.reply_text("Operation canceled. Send a new invoice photo when ready.")
        return WAIT_PHOTO
    except Exception as e:
        log_error(f"Error in cancel command: {e}", exc_info=True)
        await update.message.reply_text("An error occurred. Please try again.")
        return WAIT_PHOTO
