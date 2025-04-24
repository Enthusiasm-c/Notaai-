import datetime
import re
from typing import Dict


def format_invoice_for_display(invoice_dict: Dict) -> str:
    """
    Преобразует результат match_invoice_items (словарь) в читабельный
    текст для Telegram: шапка, таблица строк, итог.
    
    Args:
        invoice_dict: Словарь данных накладной

    Returns:
        str: Отформатированная строка для отображения

    Требования:
    * Не использовать markdown, только моноширинный текст.
    * Колонки: №, Наименование (обрезать до 22 симв), Кол-во+ед, Цена.
    * Выравнивание по ширине 60 символов.
    * Возвращает готовую строку.
    """
    # Извлекаем данные из словаря
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
    header = [
        "╔══════════════════════════════════════════════════════════╗",
        f"║ Поставщик: {vendor_name:<43}║",
        f"║ Дата: {formatted_date:<49}║",
        "╠═════╦════════════════════════╦══════════════╦═════════════╣",
        "║  №  ║ Наименование           ║ Кол-во       ║    Цена     ║",
        "╠═════╬════════════════════════╬══════════════╬═════════════╣"
    ]
    
    # Формируем строки таблицы
    rows = []
    for i, item in enumerate(items, 1):
        name = item.get("name", "")
        # Обрезаем имя до 22 символов
        name_display = name[:22] + "..." if len(name) > 22 else name.ljust(22)
        
        quantity = item.get("quantity", 0)
        unit = item.get("unit", "шт")
        price = item.get("price", 0)
        
        # Форматируем строку таблицы
        qty_str = f"{quantity} {unit}"
        row = f"║ {i:3} ║ {name_display} ║ {qty_str:12} ║ {price:11.2f} ║"
        rows.append(row)
    
    # Формируем подвал таблицы
    footer = [
        "╠═════╩════════════════════════╩══════════════╩═════════════╣",
        f"║ ИТОГО: {total_amount:52.2f} ║",
        "╚══════════════════════════════════════════════════════════╝"
    ]
    
    # Объединяем все части
    result = "\n".join(header + rows + footer)
    return result


def test_format_invoice_for_display():
    """
    Unit-тест для функции format_invoice_for_display
    """
    # Тестовые данные
    test_invoice = {
        "vendor_name": "ООО Тестовый поставщик",
        "date": "2023-05-15",
        "total_amount": 12345.67,
        "items": [
            {"name": "Товар с длинным наименованием для теста", "quantity": 10, "unit": "шт", "price": 100.50},
            {"name": "Короткий товар", "quantity": 5, "unit": "кг", "price": 2009.00},
            {"name": "Товар без единиц", "quantity": 3, "price": 100.00}
        ]
    }
    
    # Вызываем функцию форматирования
    result = format_invoice_for_display(test_invoice)
    
    # Проверки
    assert "ООО Тестовый поставщик" in result
    assert "15.05.2023" in result
    assert "12345.67" in result
    assert "Товар с длинным наимен..." in result
    assert "Короткий товар" in result
    assert "10 шт" in result
    assert "5 кг" in result
    assert "3 шт" in result
    assert "100.50" in result
    assert "2009.00" in result
    assert "100.00" in result
    
    # Проверка длины строки (должна быть 60 символов в ширину)
    lines = result.split("\n")
    for line in lines:
        assert len(line) == 60, f"Строка должна быть 60 символов: '{line}'"
    
    print("Все тесты пройдены!")
