"""
Centralised runtime settings for the Nota AI application.

* Loads values from environment variables and optionally a local `.env` file
  in the project root.
* Validates required secrets at import time, raising a clear ValueError if
  missing.
* Uses pydantic‑settings (Pydantic v2) for type‑safe access.
"""
from __future__ import annotations

from typing import List

from pydantic import (
    UUID4,
    HttpUrl,
    Field,
    AliasChoices,
    ValidationError,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

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


class Config(BaseSettings):
    """Application‑wide runtime configuration."""

    # ─────────────── mandatory secrets ────────────────
    openai_api_key: str = Field(..., validation_alias="OPENAI_API_KEY")

    telegram_token: str = Field(
        ..., validation_alias=AliasChoices("TELEGRAM_TOKEN", "TELEGRAM_BOT_TOKEN")
    )

    syrve_server_url: HttpUrl = Field(..., validation_alias="SYRVE_SERVER_URL")
    syrve_login: str = Field(..., validation_alias="SYRVE_LOGIN")
    syrve_password: str = Field(..., validation_alias="SYRVE_PASSWORD")
    default_store_id: UUID4 = Field(..., validation_alias="DEFAULT_STORE_ID")

    # ─────────────── data file paths ────────────────
    products_csv: str = Field(
        "data/base_products.csv", validation_alias="PRODUCTS_CSV"
    )
    suppliers_csv: str = Field(
        "data/base_suppliers.csv", validation_alias="SUPPLIERS_CSV"
    )
    learned_products_csv: str = Field(
        "data/learned_products.csv", validation_alias="LEARNED_PRODUCTS_CSV"
    )
    learned_suppliers_csv: str = Field(
        "data/learned_suppliers.csv", validation_alias="LEARNED_SUPPLIERS_CSV"
    )

    # ─────────────── optional tweaks ────────────────
    preview_max_lines: int = 20
    invoice_date_format: str = "%d.%m.%Y"

    # pydantic‑settings meta
    model_config = SettingsConfigDict(
        env_prefix="",  # take env‑vars as‑is
        env_file=".env",
        validate_assignment=True,
        extra="forbid",  # unknown env vars ⇒ explicit error
    )


# ─────────────── validation helper ────────────────

def _raise_on_missing(err: ValidationError) -> None:
    """Re‑shape Pydantic's ValidationError into a concise message."""

    missing: List[str] = [
        loc[0].upper() if isinstance(loc, tuple) else loc.upper()
        for loc in (e["loc"] for e in err.errors() if e["type"] == "missing")
    ]

    # Make the Telegram token hint friendlier
    missing = [
        "TELEGRAM_TOKEN or TELEGRAM_BOT_TOKEN" if k in {"TELEGRAM_TOKEN", "TELEGRAM_BOT_TOKEN"} else k
        for k in missing
    ]

    raise ValueError(
        "Missing required environment variables: " + ", ".join(sorted(set(missing)))
    ) from None


try:
    settings = Config()  # validated at import‑time
except ValidationError as exc:
    _raise_on_missing(exc)


# ─────────────── dialog‑state constants ────────────────
WAIT_PHOTO = 0
WAIT_CONFIRM = 1
CONFIRMATION = 2
ADD_NEW_ITEM = 3
EDIT_ITEM = 4
SELECT_EDIT_ITEM = 5
SET_CONVERSION = 6
FINAL_CONFIRMATION = 7
FIX_ITEM = 8
