# utils/configuration.py
"""
Centralised runtime configuration for NotaAI services.

* Reads only OS-level environment variables passed by Docker Compose
* No search for '.env' inside the image  →  avoids PermissionError
* Type-safe thanks to Pydantic v2
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=(), case_sensitive=True)
    """Runtime settings used by OCR-, Syrve- and storage-services."""

    # —————————————————      API KEYS / TOKENS      —————————————————
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    telegram_token: str = Field(
        ...,
        env=["TELEGRAM_TOKEN", "TELEGRAM_BOT_TOKEN"],  # оба имён подходят
    )

    # —————————————————      SYRVE BACKEND          —————————————————
    syrve_server_url: str = Field(..., env="SYRVE_SERVER_URL")  # e.g. https://example.syrve.online:443
    syrve_login: str = Field(..., env="SYRVE_LOGIN")
    syrve_password: str = Field(..., env="SYRVE_PASSWORD")
    default_store_id: str = Field(..., env="DEFAULT_STORE_ID")

    # —————————————————      PATHS TO CSV DATA      —————————————————
    products_csv: str = Field("data/base_products.csv", env="PRODUCTS_CSV")
    suppliers_csv: str = Field("data/base_suppliers.csv", env="SUPPLIERS_CSV")
    learned_products_csv: str = Field(
        "data/learned_products.csv", env="LEARNED_PRODUCTS_CSV"
    )

    # pydantic-settings configuration: NO .env lookup, case-sensitive env names
    model_config = SettingsConfigDict(env_file=(), case_sensitive=True)


# singleton used by the rest of the code-base
settings = Config()

__all__ = ["Config", "settings"]
