from __future__ import annotations
import inspect
from typing import Any


async def ensure_result(value: Any):
    """
    Если value — coroutine, дожидается её и возвращает результат.
    Иначе просто отдаёт value как есть.
    """
    if inspect.iscoroutine(value):
        return await value
    return value
