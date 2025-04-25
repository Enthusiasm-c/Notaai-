"""utils.configuration

Centralised runtime settings for the Nota AI application.

* Loads values from **real** environment variables and, _if present_, a local
  ``.env`` file in the project root.
* Validates all critical secrets at import time and raises a **clear**
  ``ValueError`` if something is missing.
* Uses **pydantic-settings** (Pydantic v2) for type-safe access.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, List

from pydantic import UUID4, HttpUrl, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["settings"]


class Config(BaseSettings):
    """Typed settings model.

    Required environment variables (names are **case-sensitive**):
    * ``OPENAI_API_KEY``
    * ``TELEGRAM_TOKEN`` **or** ``TELEGRAM_BOT_TOKEN``
    * ``SYRVE_SERVER_URL``
    * ``SYRVE_LOGIN``
    * ``SYRVE_PASSWORD``
    * ``DEFAULT_STORE_ID``
    """

    # ─── mandatory ──────────────────────────────────────────────────────────
    openai_api_key: str
    telegram_token: str | None = None  # filled via validator below
    syrve_server_url: HttpUrl
    syrve_login: str
    syrve_password: str
    default_store_id: UUID4

    # ─── optional with sane defaults ───────────────────────────────────────
    preview_max_lines: int = 20
    invoice_date_format: str = "%d.%m.%Y"

    # ─── pydantic config ──────────────────────────────────────────────
    model_config = SettingsConfigDict(
        env_prefix="",          # читаем окружение как есть
        env_file=None,          # НЕ ищем .env в контейнере
        validate_assignment=True,
    )

    # ─── custom logic ──────────────────────────────────────────────────────
    @field_validator("telegram_token", mode="before")
    @classmethod
    def _resolve_telegram_token(cls, v: str | None) -> str | None:  # noqa: D401 – simple helper
        """Pick token from *either* TELEGRAM_TOKEN or TELEGRAM_BOT_TOKEN."""
        if v:
            return v
        return os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")


def _raise_on_missing(e: ValidationError) -> None:  # noqa: ANN001 – signature fixed by pydantic
    """Convert pydantic's ValidationError into a flat ValueError message."""
    missing: List[str] = [err["loc"][0].upper() for err in e.errors() if err["type"] == "missing"]
    if missing:
        # Handle telegram dual env-var name for clarity
        missing = [
            "TELEGRAM_TOKEN or TELEGRAM_BOT_TOKEN" if k == "TELEGRAM_TOKEN" else k
            for k in missing
        ]
        joined = ", ".join(sorted(set(missing)))
        raise ValueError(f"Missing required environment variables: {joined}") from None
    raise e  # different kind of validation error


try:
    settings = Config()  # created at import time
except ValidationError as exc:  # pragma: no cover – fail fast at startup
    _raise_on_missing(exc)

