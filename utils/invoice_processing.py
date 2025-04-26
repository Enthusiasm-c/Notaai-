"""
utils/invoice_processing.py

Обработка и обогащение накладных после OCR.

- Унификация структуры данных.
- Добавление статусов matched/unmatched.
- Форматирование для отображения в Telegram.
"""

import asyncio
import datetime as dt
from textwrap import shorten
from typing import Any, Dict, List, Tuple

from rapidfuzz import fuzz, process

from utils.match import load_products_db, load_suppliers_db

# Порог для fuzzy matching
MATCH_THRESHOLD = 85

# Загружаем базы продуктов и поставщиков один раз
_PRODUCTS = load_products_db()
_SUPPLIERS = load_suppliers_db()
_PRODUCT_NAMES = [p["name"] for p in _PRODUCTS]
_SUPPLIER_NAMES = [s["name"] for s in _SUPPLIERS]


def _human_money(value: float) -> str:
    """Форматирование суммы с разделителем тысяч, без десятичных."""
    if value == 0:
        return "0"
    return f"{value:,.0f}".replace(",", " ")  # неразрывный пробел


def _unit_to_display(raw: str) -> str:
    """Нормализация единиц измерения."""
    mapping = {
        "kg": "kg",
        "ltr": "ltr",
        "pcs": "pcs",
        "pack": "pack",
        "box": "box",
        "crt": "crt",
        "bil": "bil",
        "gln": "gln",
    }
    return mapping.get(raw.lower().strip(), raw)


async def _match_products(items: List[Dict[str, Any]]) -> None:
    """Добавляет product_id и match_score к каждому item."""
    for item in items:
        name = item.get("name", "").lower()
        choice, score, idx = process.extractOne(name, _PRODUCT_NAMES, scorer=fuzz.WRatio) or (None, 0, None)
        if score >= MATCH_THRESHOLD and idx is not None:
            prod = _PRODUCTS[idx]
            item["product_id"] = prod["id"]
            item["match_score"] = score
        else:
            item["product_id"] = None
            item["match_score"] = score


async def _match_supplier(name: str | None) -> Tuple[str | None, bool]:
    """Фаззи-матчинг поставщика."""
    if not name:
        return None, False
    choice, score, idx = process.extractOne(name.lower(), _SUPPLIER_NAMES, scorer=fuzz.WRatio) or (None, 0, None)
    if score >= MATCH_THRESHOLD and idx is not None:
        return _SUPPLIERS[idx]["id"], True
    return None, False


async def enrich_invoice(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """
    Обогащает накладную: матчит продукты и поставщика, добавляет статусы.

    Вход: словарь с ключами:
        - supplier (str)
        - items (list of dicts с ключами name, qty, unit, price и др.)

    Выход: словарь с унифицированными ключами и статусами.
    """
    items = parsed.get("items", [])

    # Унифицируем поля qty → quantity
    for item in items:
        if "qty" in item:
            item["quantity"] = float(item.pop("qty"))
        else:
            item["quantity"] = float(item.get("quantity", 0))
        item["price"] = float(item.get("price", 0))
        item["unit"] = item.get("unit", "").lower()

    await _match_products(items)
    supplier_id, supplier_ok = await _match_supplier(parsed.get("supplier"))

    # Добавляем статусы matched/unmatched и is_valid
    for item in items:
        is_valid = item["quantity"] > 0 and item["price"] > 0
        matched = item.get("product_id") is not None and is_valid
        item["match_status"] = "matched" if matched else "unmatched"
        item["is_valid"] = is_valid

    matched_count = sum(1 for i in items if i["match_status"] == "matched")
    unmatched_count = len(items) - matched_count

    enriched = {
        **parsed,
        "items": items,
        "supplier_id": supplier_id,
        "supplier_ok": supplier_ok,
        "matched_count": matched_count,
        "unmatched_count": unmatched_count,
    }
    return enriched


def _split_items(items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Разделяет items на matched и unmatched."""
    matched = [i for i in items if i.get("match_status") == "matched"]
    unmatched = [i for i in items if i.get("match_status") != "matched"]
    return matched, unmatched


def format_invoice_for_display(inv: Dict[str, Any]) -> str:
    """
    Форматирует накладную в HTML для Telegram с отметками статусов.

    Использует единый формат полей.
    """
    dt_str = inv.get("scanned_at") or dt.datetime.utcnow().strftime("%d %b %Y")
    supplier = inv.get("supplier") or "Unknown supplier"
    buyer = inv.get("buyer") or "Not found – invoice may belong to another venue"

    supplier_prefix = "✅" if inv.get("supplier_ok") else "❌"
    buyer_prefix = "✅" if inv.get("buyer") else "⚠️"

    matched, unmatched = _split_items(inv.get("items", []))

    total_matched = sum(i["quantity"] * i["price"] for i in matched)
    total_unmatched = len(unmatched)

    lines = [
        "📄 <b>Invoice</b>",
        f"Supplier: {supplier_prefix} {supplier}",
        ("[🖊️ Select supplier]" if not inv.get("supplier_ok") else ""),
        f"Buyer: {buyer_prefix} {buyer}",
        ("[🖊️ Set buyer]" if buyer_prefix != "✅" else ""),
        f"Scanned: {dt_str}",
        "",
        f"✅ Matched {len(matched)} — <b>IDR {_human_money(total_matched)}</b>",
        f"❌ Need fix {total_unmatched}",
    ]

    def _fmt_row(idx: int, item: Dict[str, Any], done: bool) -> str:
        price = _human_money(item["price"])
        qty = item["quantity"]
        unit = _unit_to_display(item["unit"])
        name = shorten(item["name"], width=18, placeholder="…")
        mark = "✓" if done else "⚠️"
        action = "" if done else f" [✏️ Fix_{idx}]"
        return f"{idx}. {name:<18} {qty:g} {unit} × {price} = 0 {mark}{action}"

    if matched:
        lines.append("\n--- MATCHED ({} ) ---".format(len(matched)))
        for idx, item in enumerate(matched, 1):
            lines.append(_fmt_row(idx, item, True))

    if unmatched:
        lines.append("\n--- NEED FIX ({}) ---".format(len(unmatched)))
        offset = len(matched)
        for idx, item in enumerate(unmatched, 1):
            lines.append(_fmt_row(offset + idx, item, False))

    lines.append("\nReview the data and fix any issues.")
    return "\n".join(filter(None, lines))


def ensure_result(obj: Any) -> Dict[str, Any]:
    """
    Утилита для unwrap coroutine или passthrough dict.
    """
    if asyncio.iscoroutine(obj):
        return asyncio.run(obj)
    if obj is None:
        return {}
    return obj
