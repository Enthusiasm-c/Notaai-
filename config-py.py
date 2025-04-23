import os
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

# Состояния диалога
WAIT_PHOTO = 0
WAIT_CONFIRM = 1
user_data = {}  # Словарь для хранения данных пользователей: dict[int, dict]

# Конфигурация бота
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is not set")

# Конфигурация OpenAI API
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4o')

# Конфигурация Syrve API
SYRVE_LOGIN = os.environ.get('SYRVE_LOGIN')
SYRVE_PASSWORD = os.environ.get('SYRVE_PASSWORD')
SYRVE_BASE_URL = os.environ.get('SYRVE_BASE_URL', 'https://api.syrve.com/api/v2')

# Конфигурация Redis
REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')