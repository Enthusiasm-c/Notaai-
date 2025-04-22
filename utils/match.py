import os
import csv
import logging
import difflib
from typing import Tuple, Optional, List, Dict

# Получаем логгер
logger = logging.getLogger(__name__)

# Путь к файлу с базой товаров
PRODUCTS_FILE = os.path.join('data', 'base_products.csv')

# Кэш для базы товаров
_products_cache: List[Dict[str, str]] = []

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
        with open(PRODUCTS_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                products.append({
                    'id': row.get('id', ''),
                    'name': row.get('name', ''),
                    'category': row.get('category', '')
                })
        
        # Сохраняем в кэш
        _products_cache = products
        logger.info(f"Loaded {len(products)} products from {PRODUCTS_FILE}")
        return products
    except Exception as e:
        logger.error(f"Error loading products: {e}", exc_info=True)
        return []

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
        product_name = product.get('name', '').lower().strip()
        
        if product_name == item_name_lower:
            # Нашли точное совпадение
            logger.info(f"Exact match for '{item_name}': {product.get('name')}")
            return product.get('id'), 1.0
    
    # Если точное совпадение не найдено, используем нечеткое сопоставление
    for product in products:
        product_name = product.get('name', '').lower().strip()
        
        # Используем алгоритм SequenceMatcher для нечеткого сопоставления
        score = difflib.SequenceMatcher(None, item_name_lower, product_name).ratio()
        
        # Обновляем лучшее совпадение, если текущее лучше
        if score > best_score:
            best_match = product
            best_score = score
    
    # Проверяем, превышает ли лучшее совпадение порог
    if best_score >= threshold and best_match:
        logger.info(f"Best match for '{item_name}': {best_match.get('name')} (score: {best_score:.2f})")
        return best_match.get('id'), best_score
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
        if product.get('id') == product_id:
            return product
    
    return None

def save_product(product_id: str, product_name: str, category: str = '') -> bool:
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
        mode = 'a' if file_exists else 'w'
        
        # Добавляем товар в файл
        with open(PRODUCTS_FILE, mode, newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Записываем заголовки, если файл новый
            if not file_exists:
                writer.writerow(['id', 'name', 'category'])
            
            # Записываем товар
            writer.writerow([product_id, product_name, category])
        
        # Добавляем товар в кэш
        global _products_cache
        if _products_cache is not None:
            _products_cache.append({
                'id': product_id,
                'name': product_name,
                'category': category
            })
        
        logger.info(f"Saved new product: {product_name} (ID: {product_id})")
        return True
    except Exception as e:
        logger.error(f"Error saving product: {e}", exc_info=True)
        return False
