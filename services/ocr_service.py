import asyncio
import base64
import datetime
import json
import logging
import os

import aiohttp
from dotenv import load_dotenv

from utils.error_handling import log_error

# Загрузка переменных окружения
load_dotenv()

# Получаем API-ключ OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Получаем логгер
logger = logging.getLogger(__name__)

# Улучшенный промпт для OCR
OCR_PROMPT = """
Analyze this invoice image and extract the following information:
1. Supplier name
2. Invoice date (format as YYYY-MM-DD)
3. All items in the invoice with their details

Return JSON with supplier, date (YYYY-MM-DD) and for each table row:
line_number, original_item_name, qty, unit, price.
Do NOT translate item names. Keep original spelling and units exactly as they appear.

Format as:
{
  "supplier": "Supplier Name",
  "date": "YYYY-MM-DD",
  "lines": [
    {
      "line": 1,
      "name": "Original Item Name",
      "qty": 10.5,
      "unit": "kg",
      "price": 100.50
    },
    ...
  ]
}
"""


async def extract(image_bytes):
    """
    Извлекает данные из изображения с помощью OpenAI Vision API

    Args:
        image_bytes: Байты изображения

    Returns:
        dict: Извлеченные данные в формате JSON
    """
    if not OPENAI_API_KEY:
        error_msg = "OpenAI API key not found in environment variables"
        log_error(error_msg)
        raise ValueError(error_msg)

    try:
        # Преобразуем изображение в base64
        base64_image = base64.b64encode(image_bytes).decode("utf-8")

        # Формируем запрос к API
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}",
        }

        # Создаем payload для API
        payload = {
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant specializing in reading invoices and extracting structured data.",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": OCR_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            },
                        },
                    ],
                },
            ],
            "max_tokens": 4000,
        }

        # Отправляем запрос к API
        logger.info("Sending request to OpenAI API")
        start_time = datetime.datetime.now()

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
            ) as response:
                if response.status != 200:
                    response_text = await response.text()
                    error_msg = (
                        f"OpenAI API returned status {response.status}: {response_text}"
                    )
                    log_error(error_msg)
                    raise Exception(error_msg)

                response_data = await response.json()

        # Рассчитываем время выполнения запроса
        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"OpenAI API response received in {duration:.2f} seconds")

        # Извлекаем текст ответа
        content = response_data["choices"][0]["message"]["content"]

        # Находим JSON в ответе
        try:
            # Ищем JSON в ответе
            json_start = content.find("{")
            json_end = content.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                json_text = content[json_start:json_end]
                extracted_data = json.loads(json_text)
            else:
                # Если JSON не найден в стандартном формате, пытаемся извлечь весь ответ как JSON
                extracted_data = json.loads(content)

            logger.info(
                f"Successfully extracted data: {len(extracted_data.get('lines', []))} lines"
            )

            # Нормализуем данные
            normalize_extracted_data(extracted_data)

            return extracted_data

        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse JSON from OpenAI response: {e}"
            log_error(error_msg)

            # Сохраняем полный ответ для отладки
            error_dir = "logs/errors/ocr_responses"
            os.makedirs(error_dir, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            with open(
                f"{error_dir}/response_{timestamp}.txt", "w", encoding="utf-8"
            ) as f:
                f.write(content)

            # Возвращаем пустую структуру
            return {
                "supplier": "Unknown",
                "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                "lines": [],
            }

    except Exception as e:
        error_msg = f"Error extracting data from image: {e}"
        log_error(error_msg, exc_info=True)

        # Возвращаем пустую структуру при ошибке
        return {
            "supplier": "Unknown",
            "date": datetime.datetime.now().strftime("%Y-%m-%d"),
            "lines": [],
        }


def normalize_extracted_data(data):
    """
    Нормализует извлеченные данные

    Args:
        data: Извлеченные данные
    """
    # Проверяем наличие обязательных полей
    if "supplier" not in data:
        data["supplier"] = "Unknown"

    if "date" not in data:
        data["date"] = datetime.datetime.now().strftime("%Y-%m-%d")

    if "lines" not in data:
        data["lines"] = []

    # Нормализуем данные о товарах
    for i, line in enumerate(data["lines"]):
        # Добавляем номер строки, если его нет
        if "line" not in line:
            line["line"] = i + 1

        # Проверяем наличие обязательных полей
        if "name" not in line:
            line["name"] = f"Item {line['line']}"

        # Проверяем и конвертируем числовые поля
        if "qty" in line:
            try:
                line["qty"] = float(line["qty"])
            except (ValueError, TypeError):
                line["qty"] = 1.0
        else:
            line["qty"] = 1.0

        if "price" in line:
            try:
                line["price"] = float(line["price"])
            except (ValueError, TypeError):
                line["price"] = 0.0
        else:
            line["price"] = 0.0

        # Добавляем единицу измерения, если ее нет
        if "unit" not in line:
            line["unit"] = "шт"
