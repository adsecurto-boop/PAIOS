"""The GUI is REST-only: it may import nothing from paios at all.

Stronger than the API's rule (which allows facade + parsing types): the
GUI's allowed imports are the stdlib, PySide6, and paios_gui itself.
File access is equally forbidden — no open()/pathlib/json-file reads;
the only I/O primitive is urllib inside client.py.
"""

import ast
import sys
from pathlib import Path

import paios_gui

ALLOWED_TOP_LEVEL = {"PySide6", "paios_gui"}
#: File/persistence modules the presentation layer must never touch.
FORBIDDEN_STDLIB = {"pathlib", "sqlite3", "shelve", "pickle", "dbm"}


def _gui_modules():
    package_dir = Path(paios_gui.__file__).parent
    return sorted(package_dir.glob("*.py"))


def _imports(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            yield node.module or ""


class TestForbiddenImports:
    def test_no_paios_backend_imports_anywhere(self):
        for module_path in _gui_modules():
            tree = ast.parse(module_path.read_text(encoding="utf-8"))
            for name in _imports(tree):
                top_level = name.split(".")[0]
                assert top_level != "paios", (
                    f"{module_path.name} imports {name!r} — the GUI must"
                    " reach PAIOS only through REST"
                )
                assert (
                    top_level in ALLOWED_TOP_LEVEL
                    or top_level in sys.stdlib_module_names
                ), f"{module_path.name} imports unexpected {name!r}"

    def test_no_file_or_store_access(self):
        for module_path in _gui_modules():
            source = module_path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            for name in _imports(tree):
                assert name.split(".")[0] not in FORBIDDEN_STDLIB, (
                    f"{module_path.name} imports {name!r}"
                )
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    called = getattr(node.func, "id", "")
                    assert called != "open", (
                        f"{module_path.name} calls open() — the GUI never"
                        " touches files"
                    )

    def test_urllib_confined_to_client(self):
        for module_path in _gui_modules():
            if module_path.name == "client.py":
                continue
            tree = ast.parse(module_path.read_text(encoding="utf-8"))
            for name in _imports(tree):
                assert not name.startswith("urllib"), (
                    f"{module_path.name} performs HTTP outside client.py"
                )
