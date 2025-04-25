import os
import csv
import logging
import difflib
from typing import Tuple, Optional, List, Dict

# Получаем логгер
logger = logging.getLogger(__name__)

# Путь к файлу с базой товаров
PRODUCTS_FILE = os.path.join("data", "base_products.csv")
SUPPLIERS_FILE = os.path.join("data", "suppliers.csv")
BUYERS_FILE = os.path.join("data", "buyers.csv")
UNITS_FILE = os.path.join("data", "canonical_units.csv")

# Кэш для баз данных
_products_cache: List[Dict[str, str]] = []
_suppliers_cache: List[Dict[str, str]] = []
_buyers_cache: List[Dict[str, str]] = []
_units_cache: List[str] = []


def load_products() -> List[Dict[str, str]]:
    """
    Загружает базу товаров из CSV-файла

    Returns:
        list: Список товаров
    """
    global _products_cache

    # Если кэш не пуст, используем его
    if _products_cache:
        return _products_cache

    # Проверяем наличие файла
    if not os.path.exists(PRODUCTS_FILE):
        logger.warning(f"Products file not found: {PRODUCTS_FILE}")
        return []

    try:
        products = []
        with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                products.append(
                    {
                        "id": row.get("id", ""),
                        "name": row.get("name", ""),
                        "category": row.get("category", ""),
                    }
                )

        # Сохраняем в кэш
        _products_cache = products
        logger.info(f"Loaded {len(products)} products from {PRODUCTS_FILE}")
        return products
    except Exception as e:
        logger.error(f"Error loading products: {e}", exc_info=True)
        return []


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


def load_buyers() -> List[Dict[str, str]]:
    """
    Загружает базу покупателей из CSV-файла

    Returns:
        list: Список покупателей
    """
    global _buyers_cache

    # Если кэш не пуст, используем его
    if _buyers_cache:
        return _buyers_cache

    # Проверяем наличие файла
    if not os.path.exists(BUYERS_FILE):
        logger.warning(f"Buyers file not found: {BUYERS_FILE}")
        return []

    try:
        buyers = []
        with open(BUYERS_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                buyers.append(
                    {
                        "id": row.get("id", ""),
                        "name": row.get("name", ""),
                    }
                )

        # Сохраняем в кэш
        _buyers_cache = buyers
        logger.info(f"Loaded {len(buyers)} buyers from {BUYERS_FILE}")
        return buyers
    except Exception as e:
        logger.error(f"Error loading buyers: {e}", exc_info=True)
        return []


def load_canonical_units() -> List[str]:
    """
    Загружает список канонических единиц измерения из CSV-файла

    Returns:
        list: Список единиц измерения
    """
    global _units_cache

    # Если кэш не пуст, используем его
    if _units_cache:
        return _units_cache

    # Проверяем наличие файла
    if not os.path.exists(UNITS_FILE):
        logger.warning(f"Units file not found: {UNITS_FILE}")
        return ["kg", "pcs", "pack", "box", "g", "ml", "l"]  # Default units

    try:
        units = []
        with open(UNITS_FILE, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if row:
                    units.append(row[0])

        # Сохраняем в кэш
        _units_cache = units
        logger.info(f"Loaded {len(units)} canonical units from {UNITS_FILE}")
        return units
    except Exception as e:
        logger.error(f"Error loading canonical units: {e}", exc_info=True)
        return ["kg", "pcs", "pack", "box", "g", "ml", "l"]  # Default units


def match(item_name: str, threshold: float = 0.6) -> Tuple[Optional[str], float]:
    """
    Сопоставляет название товара с базой данных

    Args:
        item_name: Название товара
        threshold: Порог схожести (от 0 до 1)

    Returns:
        tuple: (ID товара, оценка схожести) или (None, 0) если не найдено
    """
    # Загружаем базу товаров
    products = load_products()

    if not products:
        logger.warning("No products available for matching")
        return None, 0

    best_match = None
    best_score = 0

    # Нормализуем название товара
    item_name_lower = item_name.lower().strip()

    # Ищем точное совпадение
    for product in products:
        product_name = product.get("name", "").lower().strip()

        if product_name == item_name_lower:
            # Нашли точное совпадение
            logger.info(f"Exact match for '{item_name}': {product.get('name')}")
            return product.get("id"), 1.0

    # Если точное совпадение не найдено, используем нечеткое сопоставление
    for product in products:
        product_name = product.get("name", "").lower().strip()

        # Используем алгоритм SequenceMatcher для нечеткого сопоставления
        score = difflib.SequenceMatcher(None, item_name_lower, product_name).ratio()

        # Обновляем лучшее совпадение, если текущее лучше
        if score > best_score:
            best_match = product
            best_score = score

    # Проверяем, превышает ли лучшее совпадение порог
    if best_score >= threshold and best_match:
        logger.info(
            f"Best match for '{item_name}': {best_match.get('name')} (score: {best_score:.2f})"
        )
        return best_match.get("id"), best_score
    else:
        logger.info(f"No match found for '{item_name}' (best score: {best_score:.2f})")

        return None, 0


def get_product_by_id(product_id: str) -> Optional[Dict[str, str]]:
    """
    Возвращает информацию о товаре по его ID

    Args:
        product_id: ID товара

    Returns:
        dict: Информация о товаре или None, если товар не найден
    """
    # Загружаем базу товаров
    products = load_products()

    # Ищем товар по ID
    for product in products:
        if product.get("id") == product_id:
            return product

    return None


def save_product(product_id: str, product_name: str, category: str = "") -> bool:
    """
    Сохраняет новый товар в базу данных

    Args:
        product_id: ID товара
        product_name: Название товара
        category: Категория товара

    Returns:
        bool: Успешно ли сохранен товар
    """
    try:
        # Проверяем наличие файла
        file_exists = os.path.exists(PRODUCTS_FILE)

        # Создаем директорию, если ее нет
        os.makedirs(os.path.dirname(PRODUCTS_FILE), exist_ok=True)

        # Режим записи зависит от того, существует ли файл
        mode = "a" if file_exists else "w"

        # Добавляем товар в файл
        with open(PRODUCTS_FILE, mode, newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Записываем заголовки, если файл новый
            if not file_exists:
                writer.writerow(["id", "name", "category"])

            # Записываем товар
            writer.writerow([product_id, product_name, category])

        # Добавляем товар в кэш
        if _products_cache is not None:
            _products_cache.append({"id": product_id, "name": product_name, "category": category})

        logger.info(f"Saved new product: {product_name} (ID: {product_id})")
        return True
    except Exception as e:
        logger.error(f"Error saving product: {e}", exc_info=True)
        return False


def is_valid_unit(unit: str) -> bool:
    """
    Проверяет, является ли единица измерения канонической

    Args:
        unit: Единица измерения для проверки

    Returns:
        bool: True, если единица измерения валидна
    """
    canonical_units = load_canonical_units()
    return unit.lower() in [u.lower() for u in canonical_units]


async def match_products(items: List[Dict]) -> List[Dict]:
    """
    Сопоставляет список товаров с базой данных

    Args:
        items: Список товаров для сопоставления

    Returns:
        list: Список обогащенных товаров с результатами сопоставления
    """
    # Создаем копию списка товаров
    enriched_items = []
    
    # Обрабатываем каждый товар
    for item in items:
        # Создаем копию товара
        enriched_item = item.copy()
        
        # Получаем название товара
        item_name = item.get("name", "")
        
        if not item_name:
            enriched_item["match_score"] = 0
            enriched_item["product_id"] = None
            enriched_item["match_status"] = "unmatched"
            enriched_items.append(enriched_item)
            continue
        
        # Проверяем валидность единицы измерения
        unit = item.get("unit", "")
        if unit and not is_valid_unit(unit):
            enriched_item["match_score"] = 0
            enriched_item["product_id"] = None
            enriched_item["match_status"] = "unmatched"
            enriched_items.append(enriched_item)
            continue
        
        # Сопоставляем товар с базой данных
        product_id, score = match(item_name, threshold=0.6)
        
        # Добавляем результаты сопоставления
        enriched_item["match_score"] = score
        
        # Если оценка сопоставления выше порога, добавляем ID товара
        if score >= 0.6 and product_id:
            enriched_item["product_id"] = product_id
            enriched_item["match_status"] = "matched"
            
            # Добавляем дополнительную информацию о товаре
            product_data = get_product_by_id(product_id)
            if product_data:
                # Добавляем дополнительные данные товара, если они ещё не заданы
                for key, value in product_data.items():
                    if key not in enriched_item:
                        enriched_item[key] = value
        else:
            enriched_item["product_id"] = None
            enriched_item["match_status"] = "unmatched"
        
        # Добавляем обогащенный товар в результирующий список
        enriched_items.append(enriched_item)
    
    return enriched_items


async def match_supplier_buyer(vendor_name: str, buyer_name: str) -> Dict:
    """
    Сопоставляет названия поставщика и покупателя с базой данных

    Args:
        vendor_name: Название поставщика
        buyer_name: Название покупателя

    Returns:
        dict: Результаты сопоставления
    """
    # Загружаем базы данных
    suppliers = load_suppliers()
    buyers = load_buyers()
    
    # Инициализируем результат
    result = {
        "vendor_id": None,
        "vendor_name": vendor_name,
        "buyer_id": None,
        "buyer_name": buyer_name,
        "vendor_confidence": 0,
        "buyer_confidence": 0,
    }
    
    # Сопоставляем поставщика
    if vendor_name:
        best_vendor_score = 0
        best_vendor_match = None
        
        for supplier in suppliers:
            supplier_name = supplier.get("name", "").lower().strip()
            vendor_name_lower = vendor_name.lower().strip()
            
            # Проверяем точное совпадение
            if supplier_name == vendor_name_lower:
                best_vendor_match = supplier
                best_vendor_score = 1.0
                break
            
            # Используем нечеткое сопоставление
            score = difflib.SequenceMatcher(None, vendor_name_lower, supplier_name).ratio()
            
            if score > best_vendor_score:
                best_vendor_score = score
                best_vendor_match = supplier
        
        # Если нашли совпадение с достаточной уверенностью
        if best_vendor_score >= 0.6 and best_vendor_match:
            result["vendor_id"] = best_vendor_match.get("id")
            result["vendor_name"] = best_vendor_match.get("name")
            result["vendor_confidence"] = best_vendor_score
    
    # Сопоставляем покупателя
    if buyer_name:
        best_buyer_score = 0
        best_buyer_match = None
        
        for buyer in buyers:
            buyer_db_name = buyer.get("name", "").lower().strip()
            buyer_name_lower = buyer_name.lower().strip()
            
            # Проверяем точное совпадение
            if buyer_db_name == buyer_name_lower:
                best_buyer_match = buyer
                best_buyer_score = 1.0
                break
            
            # Используем нечеткое сопоставление
            score = difflib.SequenceMatcher(None, buyer_name_lower, buyer_db_name).ratio()
            
            if score > best_buyer_score:
                best_buyer_score = score
                best_buyer_match = buyer
        
        # Если нашли совпадение с достаточной уверенностью
        if best_buyer_score >= 0.6 and best_buyer_match:
            result["buyer_id"] = best_buyer_match.get("id")
            result["buyer_name"] = best_buyer_match.get("name")
            result["buyer_confidence"] = best_buyer_score
    
    return result
