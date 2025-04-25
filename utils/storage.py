from __future__ import annotations

import datetime as dt
import os
import re
import tempfile
from pathlib import Path
from typing import Union

__all__ = ["save_temp_file", "TEMP_DIR"]

# Вся времянка → /tmp/notaai/temp
TEMP_DIR = Path("/tmp/notaai/temp")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

_NUL_RE = re.compile(r"\x00")


def _sanitize(component: str) -> str:
    """Убирает NUL-байты и / из строки, чтобы она стала безопасной частью пути."""
    component = _NUL_RE.sub("", component)
    return component.replace(os.sep, "_")


async def save_temp_file(user_id: Union[int, str], data: bytes, *, suffix: str = ".bin") -> str:
    """
    Сохраняет бинарные данные во временный файл.

    • Сокращает вероятность ValueError, удаляя NUL-байты из suffix.
    • Имя файла:  <user>_<timestamp>.<suffix>
    • Возвращает абсолютный путь.
    """
    clean_suffix = _sanitize(suffix) or ".bin"

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = f"{user_id}_{timestamp}_"

    with tempfile.NamedTemporaryFile(
        dir=TEMP_DIR,
        prefix=prefix,
        suffix=clean_suffix,
        delete=False,
    ) as tmp:
        tmp.write(data)
        return tmp.name
