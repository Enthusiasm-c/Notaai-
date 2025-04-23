"""
main.py — точка входа Nota AI-бота.

* Использует python-telegram-bot v20+
* Запускает polling блокирующим вызовом run_polling(close_loop=False)
  — избегаем ошибки «Cannot close a running event loop».
"""

from __future__ import annotations

import logging
import os

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from handlers.command_handlers import start_command, help_command
from handlers.invoice_handlers import handle_invoice  # ваш обработчик фото

# ──────────────────────────── конфигурация ──────────────────────────────
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Проверьте, что переменная TELEGRAM_BOT_TOKEN задана в .env")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def build_app() -> Application:
    """Создаём и конфигурируем экземпляр Application."""
    application = Application.builder().token(BOT_TOKEN).build()

    # команды
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))

    # фото накладной
    application.add_handler(MessageHandler(filters.PHOTO, handle_invoice))

    return application


def main() -> None:
    """Точка входа: конфигурируем и запускаем polling."""
    application = build_app()
    logger.info("Starting bot…")
    application.run_polling(close_loop=False)  # ← ключевой параметр
    logger.info("Bot stopped!")


if __name__ == "__main__":
    main()
