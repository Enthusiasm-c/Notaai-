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

from handlers.command_handlers import start_command, help_command
from handlers.invoice_handlers import handle_invoice, handle_invoice_callback
from handlers.item_handlers import handle_item_selection
from handlers.confirmation_handlers import handle_confirmation
from handlers.manual_item_handlers import handle_manual_item_entry, handle_manual_entry_callback
from handlers.conversion_handlers import handle_conversion_entry, handle_conversion_callback

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

    app.add_handler(CallbackQueryHandler(handle_invoice_callback, pattern="^(send_to_syrve|select_supplier|set_buyer|fix_item_).*"))
    app.add_handler(CallbackQueryHandler(handle_item_selection, pattern="^(edit_item:|back_to_main|cancel_process)$"))
    app.add_handler(CallbackQueryHandler(handle_confirmation, pattern="^(confirm_action|reject_action|final_preview|select_supplier|choose_supplier_|supplier_page_|set_buyer)$"))
    app.add_handler(CallbackQueryHandler(handle_manual_entry_callback, pattern="^(confirm_manual_new:|retry_manual:|cancel_process)$"))
    app.add_handler(CallbackQueryHandler(handle_conversion_callback, pattern="^(cancel_process|back_to_edit)$"))

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^\d+(\.\d+)?$"), handle_conversion_entry))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_manual_item_entry))

    return app


def main() -> None:
    """Запуск бота (polling + health-check)."""
    application = build_app()
    logger.info("Starting bot…")
    application.run_polling(close_loop=False)   # ← ключ!
    logger.info("Bot stopped!")


if __name__ == "__main__":
    main()
