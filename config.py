from __future__ import annotations

import os
from pathlib import Path
from typing import List

from pydantic import UUID4, AnyUrl, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class _Settings(BaseSettings):
    # обязательные переменные окружения
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    telegram_token: str = Field(..., alias="TELEGRAM_TOKEN")
    syrve_server_url: AnyUrl = Field(..., env="SYRVE_SERVER_URL")
    syrve_login: str = Field(..., env="SYRVE_LOGIN")
    syrve_password: str = Field(..., env="SYRVE_PASSWORD")
    default_store_id: UUID4 = Field(..., env="DEFAULT_STORE_ID")

    # необязательные с дефолтами
    preview_max_lines: int = 20
    invoice_date_format: str = "%d.%m.%Y"

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env" if Path(".env").is_file() else None,
        env_file_encoding="utf-8",
        validate_assignment=True,
    )

    @classmethod
    def validate(cls, values):  # type: ignore[override]
        if not values.get("telegram_token"):
            alt = os.getenv("TELEGRAM_BOT_TOKEN")
            if alt:
                values["telegram_token"] = alt
        return values


try:
    settings = _Settings()
except ValidationError as err:
    miss: List[str] = []
    for e in err.errors():
        if e["loc"][0] == "telegram_token":
            miss.append("TELEGRAM_TOKEN / TELEGRAM_BOT_TOKEN")
        else:
            miss.append(e["loc"][0].upper())
    raise RuntimeError("Missing env vars: " + ", ".join(miss)) from err

# dialog states
WAIT_PHOTO = 0
WAIT_CONFIRM = 1
CONFIRMATION = 2
ADD_NEW_ITEM = 3
EDIT_ITEM = 4
SELECT_EDIT_ITEM = 5
SET_CONVERSION = 6
FINAL_CONFIRMATION = 7
FIX_ITEM = 8

__all__ = [
    "settings",
    "WAIT_PHOTO",
    "WAIT_CONFIRM",
    "CONFIRMATION",
    "ADD_NEW_ITEM",
    "EDIT_ITEM",
    "SELECT_EDIT_ITEM",
    "SET_CONVERSION",
    "FINAL_CONFIRMATION",
    "FIX_ITEM",
]
