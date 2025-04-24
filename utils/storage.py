"""
Функции для временного сохранения загруженных пользователями файлов.
"""

from __future__ import annotations
import tempfile
from pathlib import Path
from typing import BinaryIO


def save_temp_file(file_obj: BinaryIO, suffix: str = "") -> Path:
    """
    Сохраняет объект file-like (bytes, BufferedReader…) во временный файл и
    возвращает pathlib.Path к нему.

    Parameters
    ----------
    file_obj : BinaryIO
        Поток байтов (например, `bot.get_file(...).download_as_bytearray()`).
    suffix : str, optional
        Дополнительное расширение, например ".jpg" или ".pdf".

    Returns
    -------
    pathlib.Path
        Путь к созданному файлу во временной директории.
    """
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(file_obj.read() if hasattr(file_obj, "read") else file_obj)
    tmp.close()
    return Path(tmp.name)
