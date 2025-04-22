import datetime
import json
import logging
from typing import Dict, List, Optional, Tuple

from data.learning import learned_mappings, unit_conversions
from utils.match import match

# Получаем логгер
logger = logging.getLogger(__name__)


async def match_invoice_items(invoice_data: Dict) -> Dict:
    """
    Сопоставляет товары из накладной с базой данных
    и добавляет информацию о сопоставлении в данные накладной

    Args:
        invoice_data: Словарь с данными накладной

    Returns:
        Dict: Словарь с данными накладной с добавленной информацией о сопоставлении
    """
    matched_data = invoice_data.copy()

    # Добавляем информацию о сопоставлении для каждой строки
    if "lines" in matched_data:
        for i, line in enumerate(matched_data["lines"]):
            item_name = line.get("name", "")

            # Сначала проверяем, есть ли сопоставление в обученных данных
            learned_match = learned_mappings.get(item_name.lower())
            if learned_match:
                # Используем сопоставление из обученных данных
                matched_data["lines"][i]["product_id"] = learned_match["product_id"]
                matched_data["lines"][i]["match_score"] = 1.0  # Идеальное совпадение
                matched_data["lines"][i]["learned_name"] = learned_match[
                    "corrected_name"
                ]
                logger.info(
                    f"Used learned mapping for '{item_name}' -> '{learned_match['corrected_name']}'"
                )
            else:
                # Пытаемся сопоставить с базой данных
                product_id, score = match(item_name)
                matched_data["lines"][i]["product_id"] = product_id
                matched_data["lines"][i]["match_score"] = score

    return matched_data


def apply_unit_conversions(matched_data: Dict) -> List[Dict]:
    """
    Применяет конвертации единиц измерения к сопоставленным товарам

    Args:
        matched_data: Словарь с данными накладной

    Returns:
        List[Dict]: Список примененных конвертаций
    """
    conversions_applied = []

    if "lines" not in matched_data:
        return conversions_applied

    for i, line in enumerate(matched_data["lines"]):
        product_id = line.get("product_id")
        if not product_id:
            continue

        product_name = line.get("name", "")
        qty = line.get("qty")
        unit = line.get("unit", "")

        if not qty or not unit:
            continue

        # Проверяем, есть ли конвертация для этого товара и единицы измерения
        key = (product_id, unit.lower())
        if key in unit_conversions:
            conversion = unit_conversions[key]

            # Обновляем строку с конвертированными значениями
            matched_data["lines"][i]["original_qty"] = qty
            matched_data["lines"][i]["original_unit"] = unit
            matched_data["lines"][i]["qty"] = qty * conversion["conversion_factor"]
            matched_data["lines"][i]["unit"] = conversion["target_unit"]
            matched_data["lines"][i]["conversion_applied"] = True

            # Добавляем в список примененных конвертаций
            conversions_applied.append(
                {
                    "line_index": i,
                    "product_name": product_name,
                    "product_id": product_id,
                    "original_qty": qty,
                    "original_unit": unit,
                    "converted_qty": qty * conversion["conversion_factor"],
                    "converted_unit": conversion["target_unit"],
                    "conversion_factor": conversion["conversion_factor"],
                }
            )

    return conversions_applied


def format_invoice_data(data: Dict) -> str:
    """
    Форматирует данные накладной для отображения пользователю

    Args:
        data: Словарь с данными накладной и сопоставлений

    Returns:
        str: Отформатированный текст для отображения
    """
    invoice_data = data["invoice_data"]
    matched_data = data["matched_data"]
    conversions_applied = data.get("conversions_applied", [])

    # Подсчитываем количество сопоставленных товаров
    total_items = len(matched_data.get("lines", []))
    matched_items = sum(
        1
        for line in matched_data.get("lines", [])
        if line.get("product_id") is not None
    )
    unmatched_items = total_items - matched_items

    result = []
    result.append(
        f"📑 Invoice from supplier: {invoice_data.get('supplier', 'Not specified')}"
    )
    result.append(f"📆 Date: {invoice_data.get('date', 'Not specified')}\n")

    result.append(f"📊 General information:")
    result.append(f"- Total items in invoice: {total_items}")
    result.append(f"- Automatically matched: {matched_items}")
    result.append(f"- Need verification: {unmatched_items}")

    # Показываем информацию о конвертациях единиц измерения
    if conversions_applied:
        result.append("\n🔄 Unit conversions applied:")
        for conversion in conversions_applied:
            result.append(
                f"- {conversion['product_name']}: "
                f"{conversion['original_qty']} {conversion['original_unit']} → "
                f"{conversion['converted_qty']:.2f} {conversion['converted_unit']} "
                f"(factor: {conversion['conversion_factor']})"
            )

    # Если есть неопознанные товары, показываем их подробно
    if unmatched_items > 0:
        result.append("\n❓ Unrecognized items:")
        for i, line in enumerate(matched_data.get("lines", [])):
            if line.get("product_id") is None:
                line_num = line.get("line", i + 1)
                name = line.get("name", "Unknown item")
                qty = line.get("qty", 0)
                unit = line.get("unit", "")
                price = line.get("price", 0)

                result.append(f"❓ {line_num}. {name}: {qty} {unit}, {price} IDR")

    # Показываем сопоставленные товары с обученными сопоставлениями
    learned_items = [
        line
        for line in matched_data.get("lines", [])
        if line.get("product_id") is not None and "learned_name" in line
    ]

    if learned_items:
        result.append("\n✅ Items matched from previous corrections:")
        for line in learned_items:
            line_num = line.get("line", 0)
            name = line.get("name", "Unknown item")
            learned_name = line.get("learned_name", "")
            result.append(f"✅ {line_num}. {name} → {learned_name}")

    # Показываем только количество других распознанных товаров без подробностей
    auto_matched = matched_items - len(learned_items)
    if auto_matched > 0:
        result.append(
            f"\n✅ {auto_matched} other items successfully matched with the database."
        )

    return "\n".join(result)


def format_final_invoice(data: Dict) -> str:
    """
    Форматирует итоговую накладную для предварительного просмотра перед отправкой

    Args:
        data: Словарь с данными накладной

    Returns:
        str: Отформатированный текст для отображения
    """
    invoice_data = data["invoice_data"]
    matched_data = data["matched_data"]

    result = []
    result.append(f"📋 FINAL INVOICE PREVIEW")
    result.append(f"📑 Supplier: {invoice_data.get('supplier', 'Not specified')}")
    result.append(f"📆 Date: {invoice_data.get('date', 'Not specified')}\n")

    # Подсчитываем общую сумму
    total_sum = 0

    result.append(f"📊 ITEMS:")
    result.append(
        f"{'#':<4} {'Item Name':<30} {'Qty':<10} {'Unit':<8} {'Price':<12} {'Total':<12}"
    )
    result.append("-" * 80)

    for i, line in enumerate(matched_data.get("lines", [])):
        line_num = line.get("line", i + 1)
        name = line.get("name", "Unknown item")

        # Используем конвертированные значения, если они есть
        qty = line.get("qty", 0)
        unit = line.get("unit", "")
        price = line.get("price", 0)

        # Если применена конвертация, показываем оригинальные значения в скобках
        qty_display = f"{qty}"
        if "original_qty" in line:
            qty_display = f"{qty:.2f} ({line['original_qty']} {line['original_unit']})"

        # Если есть обученное сопоставление, показываем его
        name_display = name
        if "learned_name" in line:
            name_display = f"{name} → {line['learned_name']}"

        # Расчет общей суммы для строки
        line_total = qty * price if qty is not None and price is not None else 0
        total_sum += line_total

        # Ограничиваем длину названия для форматирования
        if len(name_display) > 27:
            name_display = name_display[:24] + "..."

        result.append(
            f"{line_num:<4} {name_display:<30} {qty_display:<10} {unit:<8} {price:<12} {line_total:<12}"
        )

    result.append("-" * 80)
    result.append(f"{'TOTAL:':<45} {'':<8} {'':<12} {total_sum:<12} IDR")

    result.append("\n✅ This data will be sent to Syrve. Please review carefully.")

    return "\n".join(result)


def prepare_invoice_data_for_syrve(matched_data: Dict) -> Dict:
    """
    Подготавливает данные накладной для отправки в Syrve API

    Args:
        matched_data: Словарь с данными накладной

    Returns:
        Dict: Данные для отправки в API
    """
    # Создаем структуру данных для отправки
    invoice_data = {
        "number": f"INV-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "date": matched_data.get("date", datetime.datetime.now().strftime("%d.%m.%Y")),
        "supplier_id": matched_data.get("supplier_id", "7"),  # Значение по умолчанию
        "items": [],
    }

    # Добавляем товары
    for line in matched_data.get("lines", []):
        if line.get("product_id"):
            product_id = line.get("product_id")
            qty = line.get("qty", 0)
            price = line.get("price", 0)

            # Расчет суммы
            total = qty * price

            # Добавляем товар в список
            invoice_data["items"].append(
                {
                    "product_id": product_id,
                    "amount": float(qty),
                    "price": float(price),
                    "total": float(total),
                }
            )

    return invoice_data


async def check_product_exists(item_name: str) -> Tuple[bool, Optional[str]]:
    """
    Проверяет, существует ли товар с заданным названием в базе данных

    Args:
        item_name: Название товара

    Returns:
        Tuple[bool, Optional[str]]: (существует, ID_товара)
    """
    # В MVP это простое сопоставление
    # В реальной реализации будет запрос к базе данных

    # Проверяем на точное совпадение
    product_id, score = match(
        item_name, threshold=0.95
    )  # Высокий порог для "точного" совпадения

    if product_id:
        return True, product_id

    # Если нет точного совпадения, ищем близкие совпадения
    product_id, score = match(item_name, threshold=0.7)

    if product_id:
        return True, product_id

    # Совпадений не найдено
    return False, None


def save_invoice_data(user_id, matched_data):
    """
    Сохраняет данные накладной в JSON-файл

    Args:
        user_id: ID пользователя
        matched_data: Данные накладной

    Returns:
        str: Путь к сохраненному файлу
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"data/invoices/invoice_{user_id}_{timestamp}.json"

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(matched_data, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved invoice data to {filename}")
    return filename
