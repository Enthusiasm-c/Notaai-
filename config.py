"""
Конфигурация и константы для работы бота NotaAI.

Включает состояния диалога и настройки приложения, читаемые из переменных окружения.
"""
import logging
import sys
from enum import IntEnum, auto
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)


# Состояния диалога
class BotState(IntEnum):
    WAIT_PHOTO = 0          # ждём фото / PDF
    CONFIRMATION = auto()   # проверка всей накладной
    FIX_ITEM = auto()       # пользователь исправляет 1 позицию
    ADD_NEW_ITEM = auto()
    EDIT_ITEM = auto()
    SELECT_EDIT_ITEM = auto()
    SET_CONVERSION = auto()
    FINAL_CONFIRMATION = auto()


# Экспортируем BotState как отдельные константы
_m = sys.modules[__name__]
for _n, _v in BotState.__members__.items():
    setattr(_m, _n, _v)
del _m, _n, _v


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, case_sensitive=True)
    
    TELEGRAM_TOKEN: str = Field(..., description="Telegram Bot API Token")
    OPENAI_API_KEY: str = Field(..., description="OpenAI API Key")
    OPENAI_MODEL: str = Field("gpt-4o", description="OpenAI Model to use")
    
    SYRVE_LOGIN: str = Field("", description="Syrve API Login")
    SYRVE_PASSWORD: str = Field("", description="Syrve API Password")
    SYRVE_BASE_URL: str = Field("https://api.syrve.com/api/v2", description="Syrve API Base URL")
    
    REDIS_URL: str = Field("redis://redis:6379/0", description="Redis Connection URL")


# Инициализация настроек
try:
    settings = Settings()
except Exception as e:
    raise ValueError(f"Configuration error: {e}") from e


# Словарь для хранения данных пользователей
user_data = {}  # dict[int, dict]

# Пути к файлам данных
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


__all__ = ['settings', 'BotState', 'user_data', 'BASE_DIR', 'DATA_DIR'] + list(BotState.__members__)
