import datetime
import logging
import traceback
from pathlib import Path
from typing import Optional

# Получаем логгеры
logger = logging.getLogger(__name__)
error_logger = logging.getLogger("error_logger")

# Директория для логов ошибок
LOG_DIR = Path("/tmp/notaai-logs/errors/detailed")


def log_error(message: str, exc: Exception = None):
    """
    Логирование ошибок в отдельный файл и основной лог

    Args:
        message: Сообщение об ошибке
        exc: Объект исключения
    """
    if error_logger.handlers:
        error_logger.error(message, exc_info=exc)
    logger.error(message, exc_info=exc)

    # Добавляем трассировку стека в отдельный файл для более подробного анализа
    if exc:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_DIR / f"error_{timestamp}.log", "w", encoding="utf-8") as f:
            f.write(f"Error: {message}\n\n")
            traceback.print_exception(type(exc), exc, exc.__traceback__, file=f)


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
        error_images_dir = LOG_DIR.parent / "error_images"
        error_images_dir.mkdir(parents=True, exist_ok=True)
        error_image_path = error_images_dir / f"error_{user_id}_{timestamp}.jpg"
        with open(error_image_path, "wb") as f:
            f.write(photo_bytes)
        log_error(f"Saved error-causing image to {error_image_path}")
        return str(error_image_path)
    except Exception as e:
        log_error(f"Could not save error image: {e}", e)
        return None
