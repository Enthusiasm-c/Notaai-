# utils/storage.py
from __future__ import annotations
import os
import re
import tempfile
from pathlib import Path
from typing import Union

TEMP_DIR = Path("/tmp/notaai/temp")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

_NUL_RE = re.compile(r"\x00")

def _sanitize(component: str) -> str:
    """Удаляет NUL-байты и недопустимые символы из имени файла/суфикса."""
    component = _NUL_RE.sub("", component)
    return component.replace(os.sep, "_")

def save_temp_file(user_id: Union[int, str], data: bytes, *, suffix: str = ".bin") -> str:
    """
    Сохраняет бинарные данные во временный файл и
    возвращает абсолютный путь.
    """
    clean_suffix = _sanitize(suffix) or ".bin"
    tmp = tempfile.NamedTemporaryFile(
        dir=TEMP_DIR,
        suffix=clean_suffix,
        delete=False,
    )
    tmp.write(data)
    tmp.close()
    return tmp.name
