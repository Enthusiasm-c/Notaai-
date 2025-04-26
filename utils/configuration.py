"""
utils/configuration.py

Centralised runtime settings for the Nota AI application.

* Loads values from environment variables and optionally a local
  `.env` file in the project root.
* Validates required secrets at import time, raising a clear ValueError if missing.
* Uses pydantic-settings (Pydantic v2) for type-safe access.
"""

from __future__ import annotations

import os
from typing import Any, List

from pydantic import UUID4, HttpUrl, Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["settings"]


class Config(BaseSettings):
    # Mandatory environment variables
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    telegram_token: str = Field(..., env="TELEGRAM_BOT_TOKEN")
    syrve_server_url: HttpUrl = Field(..., env="SYRVE_SERVER_URL")
    syrve_login: str = Field(..., env="SYRVE_LOGIN")
    syrve_password: str = Field(..., env="SYRVE_PASSWORD")
    default_store_id: UUID4 = Field(..., env="DEFAULT_STORE_ID")

    # Additional CSV paths (с дефолтными значениями)
    products_csv: str = Field("data/base_products.csv", env="PRODUCTS_CSV")
    suppliers_csv: str = Field("data/base_suppliers.csv", env="SUPPLIERS_CSV")
    learned_products_csv: str = Field("data/learned_products.csv", env="LEARNED_PRODUCTS_CSV")
    learned_suppliers_csv: str = Field("data/learned_suppliers.csv", env="LEARNED_SUPPLIERS_CSV")

    # Optional settings
    preview_max_lines: int = 20
    invoice_date_format: str = "%d.%m.%Y"

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        validate_assignment=True,
        extra="forbid",
    )

    @field_validator("telegram_token", mode="before")
    @classmethod
    def _resolve_telegram_token(cls, v: str | None) -> str | None:
        """Pick token from TELEGRAM_BOT_TOKEN or fallback variables."""
        if v:
            return v
        return os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")


def _raise_on_missing(e: ValidationError) -> None:
    """Converts pydantic's ValidationError into a flat ValueError message."""
    missing: List[str] = [err["loc"][0].upper() for err in e.errors() if err["type"] == "missing"]
    if missing:
        # Handle telegram dual env-var name for clarity
        missing = ["TELEGRAM_TOKEN or TELEGRAM_BOT_TOKEN" if k == "TELEGRAM_TOKEN" else k for k in missing]
        joined = ", ".join(sorted(set(missing)))
        raise ValueError(f"Missing required environment variables: {joined}") from None
    raise e


try:
    settings = Config()  # created at import time
except ValidationError as exc:
    _raise_on_missing(exc)
