import logging
import os

# conversation states
WAIT_PHOTO = 0          # бот ждёт фото накладной
WAIT_CONFIRM = 1        # бот ждёт подтверждения

# простое хранилище данных пользователя (в памяти процесса)
user_data: dict[int, dict] = {}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Bot configuration
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is not set")

# OpenAI API configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")

# Syrve API configuration
SYRVE_LOGIN = os.environ.get("SYRVE_LOGIN")
SYRVE_PASSWORD = os.environ.get("SYRVE_PASSWORD")
SYRVE_BASE_URL = os.environ.get("SYRVE_BASE_URL", "https://api.syrve.com/api/v2")

# Redis configuration
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
