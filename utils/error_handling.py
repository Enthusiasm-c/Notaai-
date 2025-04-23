import datetime
import logging
import os
import traceback
from typing import Optional

# Получаем логгеры
logger = logging.getLogger(__name__)
error_logger = logging.getLogger("error_logger")

# Директория для логов ошибок
LOG_DIR = "/tmp/notaai-logs/errors/detailed"


def log_error(message, exc_info=None):
    """
    Логирование ошибок в отдельный файл и основной лог

    Args:
        message: Сообщение об ошибке
        exc_info: Информация об исключении (необязательно)
    """
    if error_logger.handlers:
        error_logger.error(message, exc_info=exc_info)
    logger.error(message, exc_info=exc_info)

    # Добавляем трассировку стека в отдельный файл для более подробного анализа
    if exc_info:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(f"{LOG_DIR}/error_{timestamp}.log", "w", encoding="utf-8") as f:
            f.write(f"Error: {message}\n\n")
            traceback.print_exception(type(exc_info), exc_info, exc_info.__traceback__, file=f)


def save_error_image(user_id: int, photo_bytes: bytes) -> Optional[str]:
    """
    Сохраняет изображение, вызвавшее ошибку, для дальнейшего анализа

    Args:
        user_id: ID пользователя
        photo_bytes: Байты изображения

    Returns:
        error_image_path: Путь к сохраненному файлу или None
    """
    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        error_images_dir = f"{LOG_DIR}/../error_images"
        os.makedirs(error_images_dir, exist_ok=True)
        error_image_path = f"{error_images_dir}/error_{user_id}_{timestamp}.jpg"
        with open(error_image_path, "wb") as f:
            f.write(photo_bytes)
        log_error(f"Saved error-causing image to {error_image_path}")
        return error_image_path
    except Exception as e:
        log_error(f"Could not save error image: {e}")
        return None
