"""
Модуль для обработки данных накладной.
"""

import logging
from typing import Dict, List, Optional, Tuple

from utils.learning import load_unit_conversions

# Получаем логгер
logger = logging.getLogger(__name__)


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
    
    logger.info("Applied {} unit conversions".format(len(conversions_applied)))
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


def match_invoice_items(invoice_data: Dict) -> Dict:
    """
    Сопоставляет товары из накладной с базой данных.

    Args:
        invoice_data: Данные накладной от OCR

    Returns:
        dict: Накладная с сопоставленными товарами
    """
    from utils.match import match
    
    # Создаем копию данных, чтобы не изменять оригинал
    matched_data = invoice_data.copy()
    
    # Преобразуем товары в формат строк для сопоставления
    lines = []
    for item in invoice_data.get("items", []):
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
            logger.info("Matched item: {} -> {} (score: {:.2f})".format(
                line["name"], product_id, score
            ))
        else:
            logger.info("No match found for item: {}".format(line["name"]))
        
        lines.append(line)
    
    # Заменяем список товаров сопоставленными
    matched_data["lines"] = lines
    
    return matched_data


def prepare_invoice_data_for_syrve(matched_data: Dict) -> Dict:
    """
    Подготавливает данные накладной для отправки в Syrve.

    Args:
        matched_data: Данные накладной с сопоставленными товарами

    Returns:
        dict: Данные в формате для Syrve API
    """
    import datetime
    
    # Базовые данные накладной
    syrve_data = {
        "date": datetime.datetime.now().strftime("%Y-%m-%d"),
        "supplier": matched_data.get("supplier", "Неизвестный поставщик"),
        "items": [],
        "total": matched_data.get("total", 0),
    }
    
    # Преобразуем товары в формат Syrve
    for line in matched_data.get("lines", []):
        if not line.get("product_id"):
            logger.warning("Skipping item without product_id: {}".format(line.get("name")))
            continue
            
        syrve_item = {
            "product_id": line["product_id"],
            "name": line["name"],
            "quantity": line["qty"],
            "unit": line["unit"],
            "price": line["price"],
        }
        syrve_data["items"].append(syrve_item)
    
    return syrve_data


def save_invoice_data(user_id: int, matched_data: Dict) -> str:
    """
    Сохраняет данные накладной в файл для истории.

    Args:
        user_id: ID пользователя
        matched_data: Данные накладной с сопоставленными товарами

    Returns:
        str: Путь к сохраненному файлу
    """
    import datetime
    import json
    import os
    
    # Создаем директорию для истории накладных, если ее нет
    history_dir = os.path.join("data", "history")
    os.makedirs(history_dir, exist_ok=True)
    
    # Генерируем имя файла с датой и ID пользователя
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = "invoice_{}_{}.json".format(user_id, timestamp)
    file_path = os.path.join(history_dir, filename)
    
    # Сохраняем данные в файл
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(matched_data, f, ensure_ascii=False, indent=2)
    
    logger.info("Saved invoice data to {}".format(file_path))
    return file_path


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
        logger.info("Product exists: {} -> {} (score: {:.2f})".format(
            product_name, product_id, score
        ))
        return True, product_id
    
    # Если товар не найден, возвращаем False и None
    logger.info("Product does not exist: {}".format(product_name))
    return False, None
