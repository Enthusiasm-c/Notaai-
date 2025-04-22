import asyncio
import json
import logging
import os

from aiohttp import web
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

# Import your bot handlers
from handlers.command import help_command, start_command
from handlers.confirmation import handle_callback_query
from handlers.invoice import handle_invoice

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

async def setup_bot():
    """Initialize and set up Telegram bot with handlers"""
    # Get bot token from environment variable
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN environment variable not set!")
        raise ValueError("TELEGRAM_TOKEN environment variable is required")

    # Create the Application
    application = Application.builder().token(token).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))

    # Add invoice handler for photos and documents
    application.add_handler(
        MessageHandler(filters.PHOTO | filters.Document.PDF, handle_invoice)
    )

    # Add callback query handler for confirmation buttons
    application.add_handler(CallbackQueryHandler(handle_callback_query))

    return application

async def ping_handler(request):
    """Health check endpoint that returns a simple status"""
    return web.Response(
        text=json.dumps({"status": "ok"}),
        content_type="application/json"
    )

async def start_web_server():
    """Start a simple web server for health checks"""
    app = web.Application()
    app.add_routes([web.get('/ping', ping_handler)])
    
    port = int(os.environ.get('PORT', 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logger.info(f"Health check endpoint running on port {port}")

async def main():
    """Main function to run both the bot and health check server"""
    # Start health check web server
    await start_web_server()
    
    # Set up and start the bot
    application = await setup_bot()
    await application.initialize()
    await application.start()
    await application.run_polling()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped!")y

