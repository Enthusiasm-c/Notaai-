"""
main.py — точка входа Nota AI.

* python-telegram-bot v20+
* run_polling(close_loop=False) — исключаем RuntimeError
"""

from __future__ import annotations

import logging
import os

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from config import CONFIRMATION
from handlers.command_handlers import start_command, help_command
from handlers.invoice_handlers import handle_invoice, handle_invoice_callback

# ───────────────────────────  конфиг  ──────────────────────────────
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN not set in environment / .env")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def build_app() -> Application:
    """Создаём и настраиваем Application."""
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.PHOTO, handle_invoice))
    
    # Добавляем обработчик для callback кнопок
    app.add_handler(CallbackQueryHandler(handle_invoice_callback, pattern="^(confirm_invoice:|edit_items:)"))

    return app


def main() -> None:
    """Запуск бота (polling + health-check)."""
    application = build_app()
    logger.info("Starting bot…")
    application.run_polling(close_loop=False)   # ← ключ!
    logger.info("Bot stopped!")


if __name__ == "__main__":
    main()
