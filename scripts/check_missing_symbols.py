#!/usr/bin/env python
"""
Проверяет, что все `from module import name` в проекте
реально находят `name` внутри `module`.

Выход:
  • 0 — нет ошибок
  • 1 — список ImportError, которые всплывут в рантайме
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path
from typing import DefaultDict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))           # чтобы импортировать локальные пакеты

# модули, которые безопасно игнорировать (тестовые, dev-tools и т. п.)
IGNORE_MODULES: set[str] = set()

errors: DefaultDict[str, List[str]] = DefaultDict(list)


def check_file(path: Path) -> None:
    tree = ast.parse(path.read_text("utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            mod_name = node.module
            if mod_name in IGNORE_MODULES:
                continue
            try:
                module = importlib.import_module(mod_name)
            except Exception as exc:               # noqa: BLE001
                errors[f"{path}:{node.lineno}"].append(
                    f"cannot import module {mod_name!r}: {exc}"
                )
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue     # пропускаем star-imports
                if not hasattr(module, alias.name):
                    errors[f"{path}:{node.lineno}"].append(
                        f"{mod_name}.{alias.name} not found"
                    )


def main() -> None:
    for py in ROOT.rglob("*.py"):
        if any(part in {"venv", ".venv", "__pypackages__"} for part in py.parts):
            continue
        check_file(py)

    if not errors:
        print("✅  No missing symbols.")
        sys.exit(0)

    print("❌  MISSING SYMBOLS:")
    for loc, msgs in errors.items():
        for msg in msgs:
            print(f"{loc}  →  {msg}")
    sys.exit(1)


if __name__ == "__main__":
    main()
