import json
import logging
from typing import Any, Dict, Union

import aiohttp

# Настройка логирования
logger = logging.getLogger(__name__)


async def post_json(payload: Dict[str, Any]) -> bool:
    """
    Отправляет JSON-данные на тестовый сервер httpbin.org/anything

    Args:
        payload: Данные накладной для отправки

    Returns:
        True, если данные успешно отправлены, False в противном случае
    """
    try:
        logger.info(f"Отправка данных на httpbin.org: {json.dumps(payload)[:100]}...")

        async with aiohttp.ClientSession() as session:
            # Отправляем POST-запрос на httpbin.org/anything
            async with session.post(
                "https://httpbin.org/anything", json=payload, timeout=15
            ) as response:
                # Получаем и логируем ответ
                response_text = await response.text()
                status_ok = response.status == 200

                logger.info(
                    f"Ответ httpbin.org: статус={response.status}, body={response_text[:100]}..."
                )

                # В будущем здесь будет интеграция с реальным Syrve API
                if status_ok:
                    logger.info("POST-запрос выполнен успешно")
                else:
                    logger.error(f"Ошибка POST-запроса: статус {response.status}")

                return status_ok

    except aiohttp.ClientError as e:
        logger.error(f"Ошибка HTTP-запроса: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при отправке данных: {e}", exc_info=True)
        return False
