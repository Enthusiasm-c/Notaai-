# utils/match.py
"""
Helper-module for product / supplier lookup & fuzzy matching.

CSV schema (minimum):
    id,name
    123e4567-e89b-12d3-a456-426614174000,Paprika Red
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Tuple

from rapidfuzz import fuzz, process

# ──────────────────────────────── paths ────────────────────────────────
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_PRODUCTS_CSV = _DATA_DIR / "base_products.csv"
_SUPPLIERS_CSV = _DATA_DIR / "base_suppliers.csv"

# ────────────────────────── CSV loaders (cached) ───────────────────────
 def _load_csv(path: Path) -> List[Dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}")
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@lru_cache(maxsize=1)
def load_products_db() -> List[Dict[str, str]]:
    """Return entire products DB (list of dicts) – cached."""
    return _load_csv(_PRODUCTS_CSV)


@lru_cache(maxsize=1)
def load_suppliers_db() -> List[Dict[str, str]]:
    """Return entire suppliers DB (list of dicts) – cached."""
    return _load_csv(_SUPPLIERS_CSV)


# ──────────────────────── helpers / look-ups ───────────────────────────
def _index_by_id(rows: List[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    return {row["id"]: row for row in rows if row.get("id")}


_PRODUCT_IDX = _index_by_id(load_products_db())
_SUPPLIER_IDX = _index_by_id(load_suppliers_db())


def get_product_by_id(pid: str) -> Dict[str, str] | None:
    """Exact lookup by product ID (UUID-string)."""
    return _PRODUCT_IDX.get(pid)


def get_supplier_by_id(sid: str) -> Dict[str, str] | None:
    """Exact lookup by supplier ID (UUID-string)."""
    return _SUPPLIER_IDX.get(sid)


# ─────────────────────────── fuzzy matching ────────────────────────────
def _build_name_list(rows: List[Dict[str, str]]) -> List[str]:
    return [row["name"] for row in rows if row.get("name")]


_PRODUCT_NAMES = _build_name_list(load_products_db())
_SUPPLIER_NAMES = _build_name_list(load_suppliers_db())


def match_product(query: str, min_score: int = 80) -> Tuple[str | None, int]:
    """
    Fuzzy-match arbitrary `query` against product names.
    Returns (product_id | None, score 0-100).
    """
    name, score, _ = process.extractOne(
        query,
        _PRODUCT_NAMES,
        scorer=fuzz.WRatio,
        score_cutoff=min_score,
    ) or (None, 0, None)

    if name:
        # find first row with that exact name
        for row in load_products_db():
            if row["name"] == name:
                return row["id"], score
    return None, score


def match_supplier(query: str, min_score: int = 90) -> Tuple[str | None, int]:
    """Same as `match_product`, but on supplier names."""
    name, score, _ = process.extractOne(
        query,
        _SUPPLIER_NAMES,
        scorer=fuzz.WRatio,
        score_cutoff=min_score,
    ) or (None, 0, None)

    if name:
        for row in load_suppliers_db():
            if row["name"] == name:
                return row["id"], score
    return None, score


# ───────────────────────── module public API ───────────────────────────
__all__ = [
    "load_products_db",
    "load_suppliers_db",
    "get_product_by_id",
    "get_supplier_by_id",
    "match_product",
    "match_supplier",
]
