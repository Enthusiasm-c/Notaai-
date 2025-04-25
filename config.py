"""
Конфигурация и константы для работы бота NotaAI.
"""
import logging
import sys

try:                            # Pydantic 2 way
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ModuleNotFoundError:     # Fallback for old images / Pydantic 1
    from pydantic import BaseSettings  # type: ignore
    SettingsConfigDict = dict        # dummy alias

from pydantic import Field          # Field доступен в обеих версиях
from enum import IntEnum, auto
from pathlib import Path


try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ModuleNotFoundError:
    from pydantic import BaseSettings  # type: ignore
    SettingsConfigDict = dict
from pydantic import Field


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


# Защита от циклического импорта
_self = sys.modules[__name__]
for _name in BotState.__members__:
    setattr(_self, _name, BotState[_name])
del _self, _name


class Settings(BaseSettings):
    TELEGRAM_TOKEN: str = Field(..., env='TELEGRAM_TOKEN')
    OPENAI_API_KEY: str = Field(..., env='OPENAI_API_KEY')
    OPENAI_MODEL: str = Field('gpt-4o', env='OPENAI_MODEL')
    SYRVE_LOGIN: str = Field('', env='SYRVE_LOGIN')
    SYRVE_PASSWORD: str = Field('', env='SYRVE_PASSWORD')
    SYRVE_BASE_URL: str = Field('https://api.syrve.com/api/v2', env='SYRVE_BASE_URL')
    REDIS_URL: str = Field('redis://redis:6379/0', env='REDIS_URL')

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Словарь для хранения данных пользователей
user_data = {}  # dict[int, dict]

# Инициализация настроек
try:
    settings = Settings()
except Exception as e:
    raise ValueError(f"Configuration error: {e}") from e

# Пути к файлам данных
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


__all__ = list(BotState.__members__) + ["BotState", "settings", "user_data", "BASE_DIR", "DATA_DIR"]
