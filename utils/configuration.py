"""
utils/configuration.py

Centralised application configuration for Nota AI.
All parameters can be overridden via **environment variables** that begin
with the prefix `NOTAAI_`.  Example:

    export NOTAAI_PREVIEW_MAX_LINES=10

──────────────────────────────────────────────────────────────────────────────
Notes
─────
* We deliberately **disable reading of `.env` files inside the Docker image**;
  only real environment variables are considered.  This prevents the classic
  “[Errno 13] Permission denied: '.env'” problem.
* Uses **pydantic-settings ≥ 2.0** (built on top of `pydantic v2`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """
    Runtime configuration for Nota AI bot and worker services.
    """
    class Config(BaseSettings):
    """Runtime configuration for Nota AI."""
    # ↓↓↓ эта строка отключает поиск .env!
    model_config = SettingsConfigDict(env_file=(), case_sensitive=True)

    # ── General ────────────────────────────────────────────────────────────
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = (
        "INFO"
    )
    PREVIEW_MAX_LINES: int = Field(
        20, description="How many invoice lines to show in preview"
    )

    # ── Telegram bot ───────────────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = Field(..., min_length=30)
    # Back-compat: allow legacy env var
    TELEGRAM_TOKEN: str | None = None

    # ── OpenAI / LLM ───────────────────────────────────────────────────────
    OPENAI_API_KEY: str = Field(..., min_length=30)
    OPENAI_MODEL: str = "gpt-4o"

    # ── Syrve integration ─────────────────────────────────────────────────
    SYRVE_SERVER_URL: str
    SYRVE_LOGIN: str
    SYRVE_PASSWORD: str

    # ── Data files (mounted in image) ──────────────────────────────────────
    PRODUCTS_CSV: Path = Path("data/base_products.csv")
    SUPPLIERS_CSV: Path = Path("data/base_suppliers.csv")
    LEARNED_PRODUCTS_CSV: Path = Path("data/learned_products.csv")

    # ── Pydantic settings ─────────────────────────────────────────────────
    model_config = SettingsConfigDict(
        env_prefix="NOTAAI_",        # all vars may be overridden with this prefix
        env_file=(),                 # disable .env lookup inside container
        case_sensitive=True,
        validate_default=True,
        extra="ignore",
    )

    # ────────────────────── Validators ────────────────────────────────────
    @field_validator("TELEGRAM_BOT_TOKEN", mode="after")
    def allow_legacy_token(
        cls, v: str, values: dict[str, object]  # noqa: D401, N805
    ) -> str:
        """
        Accept legacy `TELEGRAM_TOKEN` if `TELEGRAM_BOT_TOKEN` is empty.
        """
        if v:
            return v
        legacy = values.get("TELEGRAM_TOKEN")
        if isinstance(legacy, str) and legacy.strip():
            return legacy
        raise ValueError("TELEGRAM_BOT_TOKEN is required")

    @field_validator("PRODUCTS_CSV", "SUPPLIERS_CSV", "LEARNED_PRODUCTS_CSV")
    def csv_must_exist(
        cls, path: Path  # noqa: D401, N805
    ) -> Path:
        if not path.exists():
            raise FileNotFoundError(path)
        return path


# singletons ---------------------------------------------------------------
settings = Config()

# convenience aliases
OPENAI_API_KEY = settings.OPENAI_API_KEY
TELEGRAM_BOT_TOKEN = settings.TELEGRAM_BOT_TOKEN
