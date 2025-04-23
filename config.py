"""
config.py
Конфигурационные константы и «глобальные» данные,
которые используются во всех модулях Nota AI-бота.
"""

from __future__ import annotations
from pathlib import Path

# ───────────────────────────────
# Состояния диалога Telegram-бота
# ───────────────────────────────
WAIT_PHOTO     = 0   # бот ждёт фотографию накладной
CONFIRMATION   = 1   # ждёт подтверждения «всё верно?»
WAIT_SUPPLIER  = 2   # (пример) ждёт выбора поставщика
WAIT_CORRECTION = 3  # (пример) пользователь исправляет позиции

# Словарь сессий:  user_id -> любые данные, нужные между шагами
user_data: dict[int, dict] = {}


# ───────────────────────────────
# Пути к данным (можно менять)
# ───────────────────────────────
BASE_DIR          = Path(__file__).resolve().parent
DATA_DIR          = BASE_DIR / "data"
PRODUCTS_CSV      = DATA_DIR / "base_products.csv"
SUPPLIERS_CSV     = DATA_DIR / "base_suppliers.csv"
LEARNED_PRODUCTS  = DATA_DIR / "learned_products.csv"
LEARNED_SUPPLIERS = DATA_DIR / "learned_suppliers.csv"

# ───────────────────────────────
# Syrve (iiko) API credentials
# ───────────────────────────────
import os

SYRVE_SERVER_URL = os.getenv("SYRVE_SERVER_URL", "https://example.syrve.online")
SYRVE_LOGIN      = os.getenv("SYRVE_LOGIN", "demo")
SYRVE_PASSWORD   = os.getenv("SYRVE_PASSWORD", "demo")
DEFAULT_STORE_ID = os.getenv("DEFAULT_STORE_ID", "00000000-0000-0000-0000-000000000000")

# ───────────────────────────────
# Прочие настройки
# ───────────────────────────────
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# сколько секунд хранить фотки-черновики
TMP_PHOTO_TTL = int(os.getenv("TMP_PHOTO_TTL", "3600"))
