"""The relay is a self-contained deployable: it must import nothing from
PAIOS, exactly like the updater. This keeps it portable — copy the
``relay/`` folder to any host and run it."""

import ast
from pathlib import Path

import paios_relay


def _relay_modules():
    package_dir = Path(paios_relay.__file__).parent
    return sorted(package_dir.glob("*.py"))


def test_relay_never_imports_paios():
    for module_path in _relay_modules():
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                top = name.split(".")[0]
                assert top not in ("paios", "paios_gui", "paios_launcher"), (
                    f"{module_path.name} imports {name!r} — the relay must"
                    " stay independent of PAIOS"
                )


def test_relay_uses_only_stdlib():
    allowed = {"paios_relay"}
    import sys

    for module_path in _relay_modules():
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                top = name.split(".")[0]
                assert top in allowed or top in sys.stdlib_module_names, (
                    f"{module_path.name} imports third-party {name!r} —"
                    " the relay is stdlib-only for portability"
                )
