"""
Модуль для обработки данных накладной.

Содержит функции для форматирования, сопоставления товаров и обогащения данных накладных.
"""
import dataclasses
import datetime
import logging
import csv
import os
from typing import Any, Dict, List, Optional, Tuple

from rapidfuzz import fuzz

from utils.learning import load_unit_conversions

# Получаем логгер
logger = logging.getLogger(__name__)

# Путь к файлу с базой поставщиков
SUPPLIERS_FILE = os.path.join("data", "base_suppliers.csv")

# Кэш для базы поставщиков
_suppliers_cache: List[Dict[str, str]] = []

__all__ = [
    "apply_unit_conversions",
    "format_invoice_data",
    "format_final_invoice",
    "match_invoice_items",
    "enrich_invoice",
    "format_invoice_for_display",
    "check_product_exists",
    "extract_supplier_buyer",
    "ensure_result",
    "find_supplier",
    "load_suppliers",
]


def load_suppliers() -> List[Dict[str, str]]:
    """
    Загружает базу поставщиков из CSV-файла

    Returns:
        list: Список поставщиков
    """
    global _suppliers_cache

    # Если кэш не пуст, используем его
    if _suppliers_cache:
        return _suppliers_cache

    # Проверяем наличие файла
    if not os.path.exists(SUPPLIERS_FILE):
        logger.warning(f"Suppliers file not found: {SUPPLIERS_FILE}")
        return []

    try:
        suppliers = []
        with open(SUPPLIERS_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                suppliers.append(
                    {
                        "id": row.get("id", ""),
                        "name": row.get("name", ""),
                    }
                )

        # Сохраняем в кэш
        _suppliers_cache = suppliers
        logger.info(f"Loaded {len(suppliers)} suppliers from {SUPPLIERS_FILE}")
        return suppliers
    except Exception as e:
        logger.error(f"Error loading suppliers: {e}", exc_info=True)
        return []


def find_supplier(supplier_name: str) -> Optional[Tuple[str, str]]:
    """
    Поиск поставщика по названию с учетом опечаток (Левенштейн ≤ 2)

    Args:
        supplier_name: Название поставщика

    Returns:
        Optional[Tuple[str, str]]: (ID поставщика, название) или None, если не найден
    """
    suppliers = load_suppliers()
    if not suppliers:
        logger.warning("No suppliers available for matching")
        return None

    # Нормализуем имя поставщика
    supplier_name_lower = supplier_name.lower().strip()

    matches = []
    for supplier in suppliers:
        supplier_name_db = supplier.get("name", "").lower().strip()
        
        # Проверяем точное совпадение
        if supplier_name_lower == supplier_name_db:
            return supplier.get("id"), supplier.get("name", "")
        
        # Проверяем по расстоянию Левенштейна
        score = fuzz.ratio(supplier_name_lower, supplier_name_db)
        levenshtein_dist = len(supplier_name_lower) + len(supplier_name_db) - (score * (len(supplier_name_lower) + len(supplier_name_db)) / 100) / 2
        
        # Если расстояние Левенштейна ≤ 2
        if levenshtein_dist <= 2:
            matches.append((supplier.get("id"), supplier.get("name", ""), score))

    # Если найдено ровно одно совпадение
    if len(matches) == 1:
        supplier_id, supplier_name, score = matches[0]
        logger.info(f"Found supplier match: {supplier_name} (ID: {supplier_id}, score: {score})")
        return supplier_id, supplier_name
    
    # Если найдено несколько совпадений, логируем и возвращаем None
    if matches:
        logger.info(f"Multiple supplier matches found for '{supplier_name}': {matches}")
    else:
        logger.info(f"No supplier match found for '{supplier_name}'")
    
    return None


def apply_unit_conversions(matched_data: Dict) -> List[Dict]:
    """
    Применяет конвертацию единиц измерения к позициям накладной.

    Args:
        matched_data: Данные накладной с сопоставленными товарами

    Returns:
        list: Список применённых конвертаций
    """
    # Загружаем данные о конвертациях
    unit_conversions = load_unit_conversions()
    
    # Список для хранения информации о применённых конвертациях
    conversions_applied = []
    
    # Обрабатываем позиции в накладной
    for i, line in enumerate(matched_data.get("lines", [])):
        product_id = line.get("product_id")
        product_name = line.get("name", "")
        source_unit = line.get("unit", "")
        
        # Пропускаем, если нет ID товара или единицы измерения
        if not product_id or not source_unit:
            continue
            
        # Проверяем наличие конвертации для данной единицы измерения
        if source_unit in unit_conversions:
            conversions = unit_conversions[source_unit]
            
            # Выбираем первую подходящую конвертацию
            # В реальном сценарии здесь может быть более сложная логика выбора
            for target_unit, factor in conversions.items():
                # Применяем конвертацию
                original_qty = line.get("qty", 0)
                line["original_qty"] = original_qty
                line["original_unit"] = source_unit
                line["qty"] = original_qty * factor
                line["unit"] = target_unit
                line["conversion_applied"] = True
                
                # Сохраняем информацию о конвертации
                conversions_applied.append({
                    "line_index": i,
                    "product_name": product_name,
                    "product_id": product_id,
                    "original_qty": original_qty,
                    "original_unit": source_unit,
                    "converted_qty": original_qty * factor,
                    "converted_unit": target_unit,
                    "conversion_factor": factor,
                })
                
                # Используем только первую конвертацию
                break
    
    logger.info("Applied %d unit conversions", len(conversions_applied))
    return conversions_applied


def format_invoice_data(user_data: Dict) -> str:
    """
    Форматирует данные накладной для отображения пользователю.

    Args:
        user_data: Данные пользователя с информацией о накладной

    Returns:
        str: Отформатированный текст с данными накладной
    """
    matched_data = user_data.get("matched_data", {})
    
    # Формируем заголовок
    supplier = matched_data.get("supplier", "Unknown supplier")
    total = matched_data.get("total", 0)
    
    message = "📄 *Invoice from {}*\n\n".format(supplier)
    
    # Добавляем информацию о товарах
    message += "*Items:*\n"
    
    for i, line in enumerate(matched_data.get("lines", [])):
        line_num = line.get("line", i + 1)
        name = line.get("name", "Unknown item")
        qty = line.get("qty", 0)
        unit = line.get("unit", "")
        price = line.get("price", 0)
        product_id = line.get("product_id")
        match_score = line.get("match_score", 0)
        
        # Форматируем строку с товаром
        item_price = qty * price
        item_line = "{}. {} - {} {} × {} = {:.0f}".format(
            line_num, name, qty, unit, price, item_price
        )
        
        # Добавляем информацию о сопоставлении
        if product_id:
            status = "✅" if match_score > 0.8 else "⚠️"
            item_line += " {}".format(status)
        else:
            item_line += " ❓"
            
        message += item_line + "\n"
    
    # Добавляем информацию о конвертациях
    conversions = user_data.get("conversions_applied", [])
    if conversions:
        message += "\n*Applied conversions:*\n"
        for conv in conversions:
            message += "• {}: {} {} → {} {}\n".format(
                conv['product_name'],
                conv['original_qty'],
                conv['original_unit'],
                conv['converted_qty'],
                conv['converted_unit']
            )
    
    # Добавляем общую сумму
    formatted_total = "{:,.0f}".format(total).replace(",", " ")
    message += "\n*Total:* IDR {}".format(formatted_total)
    
    return message


def format_final_invoice(user_data: Dict) -> str:
    """
    Форматирует финальные данные накладной для подтверждения перед отправкой.

    Args:
        user_data: Данные пользователя с информацией о накладной

    Returns:
        str: Отформатированный текст с финальными данными накладной
    """
    matched_data = user_data.get("matched_data", {})
    
    # Формируем заголовок
    supplier = matched_data.get("supplier", "Unknown supplier")
    total = matched_data.get("total", 0)
    
    message = "📋 *FINAL INVOICE*\n\n"
    message += "*Supplier:* {}\n\n".format(supplier)
    
    # Добавляем таблицу товаров
    message += "*ITEMS:*\n"
    message += "```\n"
    message += "# Name                         Quantity   Price     Total     \n"
    message += "-" * 70 + "\n"
    
    for i, line in enumerate(matched_data.get("lines", [])):
        line_num = line.get("line", i + 1)
        name = line.get("name", "Unknown item")
        qty = line.get("qty", 0)
        unit = line.get("unit", "")
        price = line.get("price", 0)
        
        # Обрезаем длинные названия
        display_name = name[:27] + "..." if len(name) > 30 else name
        
        # Форматируем строку таблицы
        item_price = qty * price
        formatted_price = "{:,.0f}".format(price).replace(",", " ")
        formatted_item_price = "{:,.0f}".format(item_price).replace(",", " ")
        
        line_str = "{:<3} {:<30} {} {:<6} {:<10} {:<10}\n".format(
            line_num, display_name, qty, unit, formatted_price, formatted_item_price
        )
        message += line_str
    
    message += "-" * 70 + "\n"
    formatted_total = "{:,.0f}".format(total).replace(",", " ")
    message += "TOTAL:                                            IDR {}\n".format(formatted_total)
    message += "```\n\n"
    
    # Добавляем информацию о действиях
    message += "*Actions:*\n"
    message += "• Confirm and send to Syrve\n"
    message += "• Return to editing\n"
    message += "• Cancel and start over\n"
    
    return message


async def match_invoice_items(invoice_data) -> Dict:
    """
    Сопоставляет товары из накладной с базой данных.

    Args:
        invoice_data: Данные накладной от OCR

    Returns:
        dict: Накладная с сопоставленными товарами
    """
    from utils.match import match
    
    # Создаем копию данных, чтобы не изменять оригинал
    matched_data: Dict[str, Any] = dataclasses.asdict(invoice_data)
    
    # Преобразуем товары в формат строк для сопоставления
    lines = []
    for item in invoice_data.items:
        # Создаем базовую структуру строки
        line = {
            "name": item.get("name", ""),
            "qty": item.get("qty", 0),
            "unit": item.get("unit", ""),
            "price": item.get("price", 0),
            "product_id": None,
            "match_score": 0,
        }
        
        # Пытаемся сопоставить товар
        product_id, score = match(line["name"])
        
        if product_id and score > 0:
            line["product_id"] = product_id
            line["match_score"] = score
            logger.info("Matched item: %s -> %s (score: %.2f)", line["name"], product_id, score)
        else:
            logger.info("No match found for item: %s", line["name"])
        
        lines.append(line)
    
    # Заменяем список товаров сопоставленными
    matched_data["lines"] = lines
    
    return matched_data


async def extract_supplier_buyer(ocr_data: Dict) -> Dict:
    """
    Извлекает и сопоставляет информацию о поставщике и покупателе из результатов OCR.
    
    Args:
        ocr_data: Данные после OCR обработки
    
    Returns:
        dict: Информация о поставщике и покупателе
    """
    from utils.match import match
    
    # Извлекаем имя поставщика из OCR данных
    vendor_name = ocr_data.get("vendor_name", "")
    buyer_name = ocr_data.get("buyer_name", "")
    raw_text = ocr_data.get("raw_text", "")
    
    # Поиск покупателя Eggstra в тексте
    buyer_found = False
    if raw_text and "eggstra" in raw_text.lower():
        buyer_name = "Eggstra"
        buyer_found = True
    
    # Поиск поставщика по базе
    supplier_match = None
    if vendor_name:
        supplier_match = find_supplier(vendor_name)
    
    # Результат для поставщика
    if supplier_match:
        vendor_id, matched_vendor_name = supplier_match
        vendor_status = "matched"
        vendor_confidence = 1.0
    else:
        vendor_id = None
        vendor_status = "unmatched"
        vendor_confidence = 0.0
    
    # Формируем результат
    result = {
        "vendor_id": vendor_id,
        "vendor_name": vendor_name,
        "buyer_id": None,  # Для Eggstra не требуется ID
        "buyer_name": buyer_name if buyer_found else "",
        "vendor_confidence": vendor_confidence,
        "buyer_confidence": 1.0 if buyer_found else 0.0,
        "vendor_status": vendor_status,
        "buyer_status": "matched" if buyer_found else "unmatched",
        "buyer_found": buyer_found,
    }
    
    return result


async def enrich_invoice(parsed_invoice: Dict[str, Any]) -> Dict[str, Any]:
    """
    Обогащает данные накладной, сопоставляя с базой данных товаров
    и добавляя дополнительную информацию.
    
    Args:
        parsed_invoice: Словарь с данными накладной после OCR
    
    Returns:
        Dict[str, Any]: Обогащенные данные накладной
    """
    from utils.match import match_products
    
    # Создаем копию исходных данных
    enriched = parsed_invoice.copy()
    
    # Извлекаем и сопоставляем информацию о поставщике и покупателе
    supplier_buyer_info = await extract_supplier_buyer(parsed_invoice)
    enriched.update(supplier_buyer_info)
    
    # Получаем список товаров для сопоставления
    items = parsed_invoice.get("items", [])
    
    # Проверяем единицы измерения на валидность
    valid_units = ["kg", "pcs", "pack", "box", "liter", "g", "ml", "bottle", "can"]
    
    for item in items:
        unit = item.get("unit", "").lower()
        if unit not in valid_units:
            item["unit_valid"] = False
        else:
            item["unit_valid"] = True
    
    # Сопоставляем товары с базой данных
    enriched_items = await match_products(items)
    
    # Подсчитываем количество сопоставленных и невалидных товаров
    matched_count = 0
    unmatched_count = 0
    invalid_count = 0
    
    for item in enriched_items:
        quantity = item.get("quantity", 0)
        price = item.get("price", 0)
        
        # Проверяем на невалидность (количество или цена равны 0)
        if quantity == 0 or price == 0:
            item["is_valid"] = False
            invalid_count += 1
            unmatched_count += 1
        else:
            item["is_valid"] = True
            if item.get("match_status") == "matched":
                matched_count += 1
            else:
                unmatched_count += 1
    
    # Рассчитываем общее количество и сумму сопоставленных товаров
    total_qty_matched = sum(
        item.get("quantity", 0) for item in enriched_items
        if item.get("match_status") == "matched" and item.get("is_valid", True)
    )
    
    total_sum_matched_idr = sum(
        item.get("quantity", 0) * item.get("price", 0)
        for item in enriched_items 
        if item.get("match_status") == "matched" and item.get("is_valid", True)
    )
    
    # Заменяем список товаров обогащенными
    enriched["items"] = enriched_items
    
    # Добавляем метаданные
    enriched.update({
        "enriched_at": datetime.datetime.now().isoformat(),
        "items_count": len(enriched_items),
        "matched_count": matched_count,
        "unmatched_count": unmatched_count,
        "invalid_count": invalid_count,
        "total_qty_matched": total_qty_matched,
        "total_sum_matched_idr": total_sum_matched_idr,
    })
    
    return enriched


async def ensure_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Проверяет результат обогащения и убеждается, что все необходимые поля существуют.
    
    Args:
        result: Результат обогащения накладной
        
    Returns:
        Dict[str, Any]: Проверенный и дополненный результат
    """
    # Просто возвращаем результат, так как подразумевается, что он уже обработан
    # В реальном случае здесь могла бы быть дополнительная логика проверки
    return result


def format_invoice_for_display(invoice_dict: Dict) -> str:
    """
    Преобразует результат match_invoice_items (словарь) в читабельный
    текст для Telegram: шапка, таблица строк, итог.

    Args:
        invoice_dict: Словарь данных накладной

    Returns:
        str: Отформатированная строка для отображения
    """
    # Извлекаем основные данные
    vendor_name = invoice_dict.get("vendor_name", "Unknown supplier")
    vendor_id = invoice_dict.get("vendor_id")
    buyer_name = invoice_dict.get("buyer_name", "")
    buyer_found = invoice_dict.get("buyer_found", False)
    date = invoice_dict.get("date", datetime.datetime.now().strftime("%Y-%m-%d"))
    
    matched_count = invoice_dict.get("matched_count", 0)
    unmatched_count = invoice_dict.get("unmatched_count", 0)
    total_sum_matched_idr = invoice_dict.get("total_sum_matched_idr", 0)
    
    items = invoice_dict.get("items", [])
    
    # Форматируем дату (если задана как строка в формате YYYY-MM-DD)
    try:
        date_obj = datetime.datetime.strptime(date, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%d %b %Y")
    except (ValueError, TypeError):
        formatted_date = date
    
    # Формируем заголовок
    result = [
        "📄 <b>Invoice</b>",
    ]
    
    # Добавляем информацию о поставщике
    if vendor_id:
        supplier_display = f"{vendor_name} (ID = {vendor_id})"
        supplier_status = ""
    else:
        supplier_display = "❌ Unknown supplier"
        supplier_status = "[🖊️ Select supplier]"
    
    result.append(f"<b>Supplier</b>: {supplier_display}")
    if supplier_status:
        result.append(supplier_status)
    
    # Добавляем информацию о покупателе
    if buyer_found:
        buyer_display = f"{buyer_name}"
        buyer_status = ""
    else:
        buyer_display = "⚠️ Not found – invoice may belong to another venue"
        buyer_status = "[🖊️ Set buyer]"
    
    result.append(f"<b>Buyer</b>: {buyer_display}")
    if buyer_status:
        result.append(buyer_status)
    
    result.append(f"<b>Scanned</b>: {formatted_date}")
    result.append("")
    
    # Добавляем информацию о сопоставленных товарах
    if matched_count > 0:
        total_items = matched_count + unmatched_count
        formatted_total = "{:,.0f}".format(total_sum_matched_idr).replace(",", " ")
        result.append(f"✅ Matched {matched_count} / {total_items} lines — IDR {formatted_total}")
    
    if unmatched_count > 0:
        result.append(f"❌ Need fix {unmatched_count}")
    
    result.append("")
    
    # Списки сопоставленных и несопоставленных товаров
    matched_items = [
        item for item in items 
        if item.get("match_status") == "matched" and item.get("is_valid", True)
    ]
    unmatched_items = [
        item for item in items 
        if item.get("match_status") != "matched" or not item.get("is_valid", True)
    ]
    
    # Добавляем сопоставленные товары
    if matched_items:
        result.append("--- MATCHED ({}) ---".format(len(matched_items)))
        
        for i, item in enumerate(matched_items, 1):
            name = item.get("name", "")
            quantity = item.get("quantity", 0)
            unit = item.get("unit", "pcs")
            price = item.get("price", 0)
            total_item = quantity * price
            
            # Форматируем строку товара с точками для выравнивания
            name_dots = name + " " + "." * max(0, 20 - len(name))
            
            # Форматируем цену
            price_str = "{:,.0f}".format(price).replace(",", " ")
            total_str = "{:,.0f}".format(total_item).replace(",", " ")
            
            result.append(f"{i}. {name_dots} {quantity} {unit} × {price_str} = {total_str}")
        
        result.append("")
    
    # Добавляем несопоставленные товары
    if unmatched_items:
        result.append("--- NEED FIX ({}) ---".format(len(unmatched_items)))
        
        for i, item in enumerate(unmatched_items, len(matched_items) + 1):
            name = item.get("name", "")
            quantity = item.get("quantity", 0)
            unit = item.get("unit", "pcs")
            price = item.get("price", 0)
            total_item = quantity * price
            
            # Определяем статус товара
            status = ""
            if not item.get("is_valid", True):
                status = "⚠️"
            
            # Форматируем строку товара с точками для выравнивания
            name_dots = name + " " + "." * max(0, 20 - len(name))
            
            # Форматируем цену
            price_str = "{:,.0f}".format(price).replace(",", " ")
            total_str = "{:,.0f}".format(total_item).replace(",", " ")
            
            item_index = items.index(item)
            fix_button = f"[✏️ Fix_{item_index+1}]"
            
            result.append(f"{i}. {name_dots} {quantity} {unit} × {price_str} = {total_str} {status} {fix_button}")
    
    return "\n".join(result)


async def check_product_exists(product_name: str) -> Tuple[bool, Optional[str]]:
    """
    Проверяет существование товара в базе данных.

    Args:
        product_name: Название товара

    Returns:
        tuple: (существует ли товар, ID товара если существует)
    """
    from utils.match import match
    
    # Пытаемся найти товар в базе
    product_id, score = match(product_name)
    
    if product_id and score > 0.9:
        logger.info("Product exists: %s -> %s (score: %.2f)", product_name, product_id, score)
        return True, product_id
    
    # Если товар не найден, возвращаем False и None
    logger.info("Product does not exist: %s", product_name)
    return False, None
