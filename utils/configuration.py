"""
Модуль конфигурации для Nota AI.

Использует pydantic.BaseSettings для управления конфигурацией
и чтения параметров из переменных окружения.
"""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Config(BaseSettings):
    """
    Конфигурация приложения Nota AI.
    
    Все параметры могут быть переопределены через переменные окружения
    с префиксом NOTAAI_ (например, NOTAAI_PREVIEW_MAX_LINES).
    """
    
    # Основные настройки
    PREVIEW_MAX_LINES: int = 20
    LOCALE: str = "ru_RU"
    TMP_DIR: str = "/tmp"
    
    # Настройки OpenAI
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o"
    
    # Настройки Syrve
    SYRVE_LOGIN: Optional[str] = None
    SYRVE_PASSWORD: Optional[str] = None
    SYRVE_BASE_URL: str = "https://api.syrve.com/api/v2"
    
    # главное ─ отключить поиск .env в образе
    model_config = SettingsConfigDict(env_file=(), case_sensitive=True)
    
    # Пути для временных файлов
    DATA_DIR: Path = Field(default_factory=lambda: Path("data"))
    
    class Config:
        """
        Конфигурация для pydantic.BaseSettings
        """
        env_prefix = "NOTAAI_"
        env_file = ".env"
        env_file_encoding = "utf-8"
