# handlers/command_handlers.py
from telegram import Update
from telegram.ext import ContextTypes


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Я Nota AI. Пришлите фото накладной — распознаю и отправлю в Syrve."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "/start – начать работу\n"
        "/help  – подсказка\n"
        "Просто отправьте фото накладной — я сделаю остальное."
    )
