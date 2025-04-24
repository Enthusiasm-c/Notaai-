"""
Модуль для обработки данных накладной.

Содержит функции для форматирования, сопоставления товаров и обогащения данных накладных.
"""
import dataclasses
import datetime
import logging
from typing import Any, Dict, List, Optional, Tuple

from utils.learning import load_unit_conversions

# Получаем логгер
logger = logging.getLogger(__name__)

__all__ = [
    "apply_unit_conversions",
    "format_invoice_data",
    "format_final_invoice",
    "match_invoice_items",
    "enrich_invoice",
    "format_invoice_for_display",
    "check_product_exists",
]


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
    supplier = matched_data.get("supplier", "Неизвестный поставщик")
    total = matched_data.get("total", 0)
    
    message = "📄 *Накладная от {}*\n\n".format(supplier)
    
    # Добавляем информацию о товарах
    message += "*Товары:*\n"
    
    for i, line in enumerate(matched_data.get("lines", [])):
        line_num = line.get("line", i + 1)
        name = line.get("name", "Неизвестный товар")
        qty = line.get("qty", 0)
        unit = line.get("unit", "")
        price = line.get("price", 0)
        product_id = line.get("product_id")
        match_score = line.get("match_score", 0)
        
        # Форматируем строку с товаром
        item_price = qty * price
        item_line = "{}. {} - {} {} × {} = {:.2f}".format(
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
        message += "\n*Применённые конвертации:*\n"
        for conv in conversions:
            message += "• {}: {} {} → {} {}\n".format(
                conv['product_name'],
                conv['original_qty'],
                conv['original_unit'],
                conv['converted_qty'],
                conv['converted_unit']
            )
    
    # Добавляем общую сумму
    message += "\n*Итого:* {:.2f}".format(total)
    
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
    supplier = matched_data.get("supplier", "Неизвестный поставщик")
    total = matched_data.get("total", 0)
    
    message = "📋 *ФИНАЛЬНАЯ НАКЛАДНАЯ*\n\n"
    message += "*Поставщик:* {}\n\n".format(supplier)
    
    # Добавляем таблицу товаров
    message += "*ТОВАРЫ:*\n"
    message += "```\n"
    message += "# Наименование                   Кол-во     Цена      Сумма     \n"
    message += "-" * 70 + "\n"
    
    for i, line in enumerate(matched_data.get("lines", [])):
        line_num = line.get("line", i + 1)
        name = line.get("name", "Неизвестный товар")
        qty = line.get("qty", 0)
        unit = line.get("unit", "")
        price = line.get("price", 0)
        
        # Обрезаем длинные названия
        display_name = name[:27] + "..." if len(name) > 30 else name
        
        # Форматируем строку таблицы
        item_price = qty * price
        line_str = "{:<3} {:<30} {} {:<6} {:<10.2f} {:<10.2f}\n".format(
            line_num, display_name, qty, unit, price, item_price
        )
        message += line_str
    
    message += "-" * 70 + "\n"
    message += "ИТОГО:                                            {:.2f}\n".format(total)
    message += "```\n\n"
    
    # Добавляем информацию о действиях
    message += "*Действия:*\n"
    message += "• Подтвердить и отправить в Syrve\n"
    message += "• Вернуться к редактированию\n"
    message += "• Отменить и начать заново\n"
    
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
    
    # Получаем список товаров для сопоставления
    items = parsed_invoice.get("items", [])
    
    # Сопоставляем товары с базой данных
    enriched_items = await match_products(items)
    
    # Заменяем список товаров обогащенными
    enriched["items"] = enriched_items
    
    # Добавляем метаданные
    enriched["enriched_at"] = datetime.datetime.now().isoformat()
    enriched["items_count"] = len(enriched_items)
    enriched["items_matched"] = sum(1 for item in enriched_items if "product_id" in item and item["product_id"])
    
    return enriched


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
    vendor_name = invoice_dict.get("vendor_name", "Неизвестный поставщик")
    date = invoice_dict.get("date", datetime.datetime.now().strftime("%Y-%m-%d"))
    total_amount = invoice_dict.get("total_amount", 0)
    items = invoice_dict.get("items", [])
    
    # Форматируем дату (если задана как строка в формате YYYY-MM-DD)
    try:
        date_obj = datetime.datetime.strptime(date, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        formatted_date = date
    
    # Формируем заголовок
    result = [
        "📄 <b>Накладная</b>",
        f"<b>Поставщик:</b> {vendor_name}",
        f"<b>Дата:</b> {formatted_date}",
        ""
    ]
    
    # Формируем таблицу товаров
    result.append("<b>Товары:</b>")
    
    for i, item in enumerate(items, 1):
        name = item.get("name", "")
        quantity = item.get("quantity", 0)
        unit = item.get("unit", "шт")
        price = item.get("price", 0)
        total_item = quantity * price
        
        # Ограничиваем длину названия (не более 22 символов)
        display_name = name
        if len(name) > 22:
            display_name = name[:22] + "..."
        
        # Форматируем строку товара
        item_line = f"{i}. {display_name} - {quantity} {unit} × {price:.2f} = {total_item:.2f} руб."
        
        # Добавляем маркер сопоставления, если товар найден в базе
        if "product_id" in item and item["product_id"]:
            item_line += " ✓"
        
        result.append(item_line)
    
    # Добавляем итоговую сумму
    result.append("")
    result.append(f"<b>Итого:</b> {total_amount:.2f} руб.")
    
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
