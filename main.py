import asyncio
import os
import json
import logging
from aiohttp import web
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler

# Импорт обработчиков
from handlers.command_handlers import start_command, help_command
# Следующие импорты исключены, так как у нас нет этих модулей в данной задаче
# from handlers.invoice import handle_invoice
# from handlers.confirmation import handle_callback_query


# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


async def setup_bot():
    """Инициализация и настройка бота Telegram"""
    # Получение токена из переменных окружения
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN environment variable not set!")
        raise ValueError("TELEGRAM_TOKEN environment variable is required")

    # Создание экземпляра приложения
    application = Application.builder().token(token).build()

    # Добавление обработчиков команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))

    # Следующие обработчики исключены, так как у нас нет этих функций в данной задаче
    # application.add_handler(
    #    MessageHandler(filters.PHOTO | filters.Document.PDF, handle_invoice)
    # )
    # application.add_handler(CallbackQueryHandler(handle_callback_query))

    return application


async def ping_handler(request):
    """Обработчик запросов для проверки работоспособности"""
    return web.Response(
        text=json.dumps({"status": "ok"}),
        content_type="application/json"
    )


async def run_web_server():
    """Запуск веб-сервера для health-check endpoint"""
    app = web.Application()
    app.add_routes([web.get('/ping', ping_handler)])
    
    port = int(os.environ.get('PORT', 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logger.info(f"Health check endpoint running on port {port}")


async def main():
    """Основная функция для запуска бота и веб-сервера"""
    # Запуск веб-сервера для health-check endpoint
    await run_web_server()
    
    # Настройка и запуск бота
    application = await setup_bot()
    await application.initialize()
    await application.start()
    await application.run_polling()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped!")
