"""
utils/invoice_keyboard.py

Генерация InlineKeyboardMarkup для накладной.
"""

from typing import Dict, List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def build_invoice_keyboard(invoice: Dict) -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру для накладной с учётом статусов.

    Args:
        invoice: словарь с данными накладной (унифицированный формат)

    Returns:
        InlineKeyboardMarkup: клавиатура для Telegram
    """
    keyboard: List[List[InlineKeyboardButton]] = []

    # Кнопка выбора поставщика, если не подтверждён
    if not invoice.get("supplier_ok"):
        keyboard.append([
            InlineKeyboardButton("🖊️ Select supplier", callback_data="select_supplier")
        ])

    # Кнопка ввода покупателя, если не задан
    if not invoice.get("buyer"):
        keyboard.append([
            InlineKeyboardButton("🖊️ Set buyer", callback_data="set_buyer")
        ])

    # Кнопки исправления для unmatched или невалидных позиций
    unmatched_items = [
        (idx, item) for idx, item in enumerate(invoice.get("items", []))
        if item.get("match_status") != "matched" or not item.get("is_valid", True)
    ]

    fix_buttons: List[InlineKeyboardButton] = []
    for idx, _ in unmatched_items:
        fix_buttons.append(
            InlineKeyboardButton(f"Fix_{idx + 1}", callback_data=f"fix_item_{idx}")
        )
        # Группируем по 3 кнопки в ряд
        if len(fix_buttons) == 3:
            keyboard.append(fix_buttons)
            fix_buttons = []
    if fix_buttons:
        keyboard.append(fix_buttons)

    # Кнопка подтверждения, если всё в порядке
    if invoice.get("unmatched_count", 0) == 0 and invoice.get("supplier_ok") and invoice.get("buyer"):
        keyboard.append([
            InlineKeyboardButton("✅ Confirm & send to Syrve", callback_data="send_to_syrve")
        ])

    return InlineKeyboardMarkup(keyboard)
