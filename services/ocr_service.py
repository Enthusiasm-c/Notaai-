"""
OCR сервис для извлечения данных из фотографий накладных.
"""

import base64
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI, OpenAI

# Настройка логирования
logger = logging.getLogger(__name__)


@dataclass
class ParsedInvoice:
    """Структурированные данные, извлеченные из накладной."""
    
    supplier: str
    items: List[Dict[str, Any]] = field(default_factory=list)
    total: float = 0.0


async def extract(photo_path: str) -> Optional[ParsedInvoice]:
    """
    Извлекает данные из фотографии накладной с помощью OpenAI Vision.

    Args:
        photo_path: Путь к фотографии накладной

    Returns:
        ParsedInvoice: Структурированные данные накладной или None в случае ошибки
    """
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OPENAI_API_KEY not set in environment")
            return None
            
        # Если путь к файлу передан как строка
        if isinstance(photo_path, str):
            logger.info(f"Reading image from path: {photo_path}")
            with open(photo_path, "rb") as image_file:
                image_data = image_file.read()
        else:
            # Если переданы байты напрямую
            logger.info("Using provided image bytes")
            image_data = photo_path
            
        # Используем OpenAI Vision API для извлечения данных
        result = await process_image_with_openai(api_key, image_data)
        if not result:
            logger.warning("OpenAI Vision API failed to extract data, falling back to tesseract")
            # Здесь можно реализовать fallback на Tesseract
            # result = process_image_with_tesseract(image_data)
            # Пока возвращаем None, так как Tesseract не реализован
            return None
            
        # Преобразуем результат в ParsedInvoice
        return convert_to_parsed_invoice(result)
        
    except Exception as e:
        logger.error(f"Error extracting data from invoice: {e}", exc_info=True)
        return None


async def process_image_with_openai(api_key: str, image_data: bytes) -> Optional[Dict[str, Any]]:
    """
    Обрабатывает изображение с помощью OpenAI Vision API.

    Args:
        api_key: API ключ OpenAI
        image_data: Байты изображения

    Returns:
        dict: Извлеченные данные или None в случае ошибки
    """
    try:
        # Создаем клиент OpenAI
        client = AsyncOpenAI(api_key=api_key)
        
        # Кодируем изображение в base64
        base64_image = base64.b64encode(image_data).decode("utf-8")
        
        # Создаем промпт для извлечения данных
        prompt = """
        Извлеки всю информацию из этой накладной. 
        Верни JSON со следующими полями:
        - supplier (строка): название поставщика
        - items (массив): список товаров, каждый с полями:
          - name (строка): название товара
          - qty (число): количество
          - unit (строка): единица измерения (кг, шт, л и т.д.)
          - price (число): цена за единицу
        - total (число): общая сумма накладной
        
        В unit используй только стандартные сокращения (кг, шт, л).
        В случае сомнений в значениях вернись к изображению и проверь.
        """
        
        # Вызываем API
        logger.info("Sending image to OpenAI for processing")
        response = await client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "user", 
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        }
                    ]
                }
            ],
            max_tokens=4000,
            response_format={"type": "json_object"}
        )
        
        # Извлекаем результат
        content = response.choices[0].message.content
        if not content:
            logger.warning("Empty response from OpenAI")
            return None
            
        # Парсим JSON
        import json
        try:
            result = json.loads(content)
            logger.info(f"Successfully extracted data: {len(result.get('items', []))} items found")
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenAI response as JSON: {e}")
            return None
            
    except Exception as e:
        logger.error(f"Error processing image with OpenAI: {e}", exc_info=True)
        return None


def convert_to_parsed_invoice(data: Dict[str, Any]) -> ParsedInvoice:
    """
    Преобразует данные из OpenAI в структуру ParsedInvoice.

    Args:
        data: Данные, полученные от OpenAI

    Returns:
        ParsedInvoice: Структурированные данные накладной
    """
    # Извлекаем поставщика и общую сумму
    supplier = data.get("supplier", "")
    total = float(data.get("total", 0))
    
    # Преобразуем товары
    items = []
    for item in data.get("items", []):
        items.append({
            "name": item.get("name", ""),
            "qty": float(item.get("qty", 0)),
            "unit": item.get("unit", ""),
            "price": float(item.get("price", 0)),
            "product_id": None,  # Будет заполнено позже при сопоставлении
            "match_score": 0,    # Будет заполнено позже при сопоставлении
        })
    
    return ParsedInvoice(supplier=supplier, items=items, total=total)
