"""The notification subsystem is an observer: import-level proof.

Allowed: stdlib, its own package, and the bus vocabulary
(paios.runtime.system_events / event_bus — subscribing requires the
topic types). Forbidden: scheduler, decision engine, learning,
application, repositories, domain, kernel internals — and persistence
(an observer with no files cannot mutate anything durable).
"""

import ast
import sys
from pathlib import Path

import paios.notifications as package

ALLOWED_PAIOS = (
    "paios.notifications",
    "paios.runtime.system_events",
    "paios.runtime.event_bus",
)
FORBIDDEN_STDLIB = {"pathlib", "sqlite3", "shelve", "pickle", "dbm", "json"}
#: PySide6 may appear ONLY in the desktop provider (lazy import).
QT_ALLOWED_IN = {"desktop_provider.py"}


def _modules():
    return sorted(Path(package.__file__).parent.glob("*.py"))


def _imports(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            yield node.module or ""


class TestForbiddenImports:
    def test_observer_imports_only_the_bus_vocabulary(self):
        for module_path in _modules():
            tree = ast.parse(module_path.read_text(encoding="utf-8"))
            for name in _imports(tree):
                top = name.split(".")[0]
                if top == "paios":
                    assert name.startswith(ALLOWED_PAIOS), (
                        f"{module_path.name} imports {name!r} — observers"
                        " may know only the bus vocabulary"
                    )
                elif top == "PySide6":
                    assert module_path.name in QT_ALLOWED_IN, (
                        f"{module_path.name} imports Qt outside the"
                        " desktop provider"
                    )
                else:
                    assert top in sys.stdlib_module_names, (
                        f"{module_path.name} imports unexpected {name!r}"
                    )
                assert top not in FORBIDDEN_STDLIB, (
                    f"{module_path.name} imports persistence module"
                    f" {name!r}"
                )

    def test_no_file_access(self):
        for module_path in _modules():
            tree = ast.parse(module_path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    assert getattr(node.func, "id", "") != "open", (
                        f"{module_path.name} calls open()"
                    )

    def test_manager_holds_no_backend_references(self):
        """The manager's collaborators are the bus, providers, history."""
        from paios.notifications import NotificationManager

        manager = NotificationManager()
        attributes = set(vars(manager))
        assert attributes <= {
            "_config",
            "_providers",
            "_history",
            "_bus",
            "_last_sent",
            "delivered",
            "held_quiet",
            "deduplicated",
        }
