# scripts/find_missing_imports.py
import ast, pathlib, importlib.util, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]   # корень репо
sys.path.insert(0, str(ROOT))                        # чтобы находить local-пакеты

missing: dict[str, list[str]] = {}                  # {module: [file:line]}

for path in ROOT.rglob("*.py"):
    if "venv" in path.parts or path.name == "__init__.py":
        continue
    with open(path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=str(path))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name.split(".")[0]
                if importlib.util.find_spec(mod) is None:
                    missing.setdefault(mod, []).append(f"{path}:{node.lineno}")
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:      # абсолютный импорт
                mod = node.module.split(".")[0]
                if importlib.util.find_spec(mod) is None:
                    missing.setdefault(mod, []).append(f"{path}:{node.lineno}")

if not missing:
    print("✅  broken imports not found.")
    sys.exit(0)

print("❌  BROKEN IMPORTS:")
for mod, places in missing.items():
    for place in places:
        print(f"{place}  →  {mod}")

sys.exit(1)
