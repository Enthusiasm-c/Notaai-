"""Utility helpers for processing supplier invoices.

This module is responsible for **all final UI‑facing formatting** of an OCR‑parsed
invoice *after* it прошёл через matching‑logic.  It *does not* talk to Telegram –
it simply returns formatted strings / dicts that handlers can shove into
messages.  By concentrating all presentation‑rules here we avoid scattering
«❌ / ✅ / ⚠️» magic‑symbols across the code base and can iterate on layout
without touching the Telegram layer.

Public API (imported by handlers):

    enrich_invoice()              → async Dict  –  OCR‑parsed ➜ enriched + matched
    format_invoice_for_display()  → str        –  nice human‑readable message
    ensure_result()               → sync Dict  –  unwrap coroutine/None helpers

If you add a new helper – please also add it to __all__ below so static‑lint can
catch missing re‑exports.
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import math
from collections import defaultdict
from pathlib import Path
from textwrap import shorten
from typing import Any, Dict, List, Tuple

from rapidfuzz import fuzz, process  # fuzzy matching (requirements.txt)

from utils.match import load_products_db, load_suppliers_db

__all__ = [
    "enrich_invoice",
    "format_invoice_for_display",
    "ensure_result",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _human_money(value: float) -> str:
    """IDR with thousands‑separator – *no* decimals if value is int."""
    if value == 0:
        return "0"
    return f"{value:,.0f}".replace(",", " ")  # NB: non‑breaking space


def _unit_to_display(raw: str) -> str:
    """Normalise messy OCR units to short display labels."""
    mapping = {
        "kg": "kg",
        "ltr": "ltr",
        "pcs": "pcs",
        "pack": "pack",
        "box": "box",
        "krat": "crt",
        "bil": "bil",
        "gln": "gln",
    }
    return mapping.get(raw.lower().strip(), raw)


# ---------------------------------------------------------------------------
# 1️⃣   Matching / enrichment – keeps business logic here so UI can use it
# ---------------------------------------------------------------------------

_PRODUCTS = load_products_db()  # [{id, name_norm, unit, ...}]
_SUPPLIERS = load_suppliers_db()  # [{id, name_norm}]

_MATCH_THRESHOLD = 85  # rapidfuzz score

async def _match_products(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Attempt to attach product_id + match_score for every OCR item."""
    names = [p["name_norm"] for p in _PRODUCTS]
    for item in items:
        choice, score, idx = process.extractOne(
            query=item["name"].lower(), choices=names, scorer=fuzz.WRatio
        ) or (None, 0, None)
        if score >= _MATCH_THRESHOLD:
            prod = _PRODUCTS[idx]
            item.update(product_id=prod["id"], match_score=score)
        else:
            item.update(product_id=None, match_score=score)
    return items

async def _match_supplier(name: str | None) -> Tuple[str | None, bool]:
    if not name:
        return None, False
    names = [s["name_norm"] for s in _SUPPLIERS]
    choice, score, idx = process.extractOne(name.lower(), names, scorer=fuzz.WRatio) or (
        None,
        0,
        None,
    )
    if score >= _MATCH_THRESHOLD:
        return _SUPPLIERS[idx]["id"], True
    return None, False


async def enrich_invoice(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Async pipeline: OCR‑dict ➜ add supplier/buyer/product matches."""
    items: List[Dict[str, Any]] = parsed.get("items", [])
    await _match_products(items)
    supp_id, supp_ok = await _match_supplier(parsed.get("supplier"))
    enriched = {
        **parsed,
        "items": items,
        "supplier_id": supp_id,
        "supplier_ok": supp_ok,
    }
    return enriched


# ---------------------------------------------------------------------------
# 2️⃣   Presentation – everything Telegram sees is built here
# ---------------------------------------------------------------------------

def _split_items(items: List[Dict[str, Any]]) -> Tuple[List[Dict], List[Dict]]:
    matched, todo = [], []
    for it in items:
        (matched if it.get("product_id") else todo).append(it)
    return matched, todo


def format_invoice_for_display(inv: Dict[str, Any]) -> str:
    """Return a HTML‑ready string (Telegram) with ✅/⚠️ marks."""

    dt = inv.get("scanned_at") or _dt.datetime.utcnow().strftime("%d %b %Y")
    supplier = inv.get("supplier") or "Unknown supplier"
    buyer = inv.get("buyer") or "Not found – invoice may belong to another venue"

    supplier_prefix = "✅" if inv.get("supplier_ok") else "❌"
    buyer_prefix = "✅" if inv.get("buyer") else "⚠️"

    matched, todo = _split_items(inv["items"])

    # Totals
    total_matched = sum(it["qty"] * it["price"] for it in matched)
    total_needfix = len(todo)

    lines: List[str] = [
        "📄 <b>Invoice</b>",
        f"Supplier: {supplier_prefix} {supplier}",
        ("[🖊️ Select supplier]" if not inv.get("supplier_ok") else ""),
        f"Buyer: {buyer_prefix} {buyer}",
        ("[🖊️ Set buyer]" if buyer_prefix != "✅" else ""),
        f"Scanned: {dt}",
        "",
        f"✅ Matched {len(matched)} — <b>IDR {_human_money(total_matched)}</b>",
        f"❌ Need fix {total_needfix}",
    ]

    def _fmt_row(idx: int, it: Dict[str, Any], done: bool) -> str:
        price = _human_money(it["price"])
        qty = it["qty"]
        unit = _unit_to_display(it["unit"])
        name = shorten(it["name"], width=18, placeholder="…")
        mark = "✓" if done else "⚠️"
        action = "" if done else f" [✏️ Fix_{idx}]"
        return f"{idx}. {name:<18} {qty:g} {unit} × {price} = 0 {mark}{action}"

    # --- matched block
    if matched:
        lines.append("\n--- MATCHED ({} ) ---".format(len(matched)))
        for idx, item in enumerate(matched, 1):
            lines.append(_fmt_row(idx, item, True))

    # --- need fix block
    if todo:
        lines.append("\n--- NEED FIX ({}) ---".format(len(todo)))
        offset = len(matched)
        for j, item in enumerate(todo, 1):
            lines.append(_fmt_row(offset + j, item, False))

    lines.append("\nReview the data and fix any issues.")
    return "\n".join(filter(None, lines))


# ---------------------------------------------------------------------------
# 3️⃣   Helper to unwrap coroutine / ensure dict
# ---------------------------------------------------------------------------

def ensure_result(obj: Any) -> Dict[str, Any]:
    """`await` if coroutine, else passthrough – handy in handlers."""
    if asyncio.iscoroutine(obj):
        return asyncio.run(obj)  # handler already in thread, fine here
    if obj is None:
        return {}
    return obj
