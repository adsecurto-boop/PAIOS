"""The assistant's dependency graph, enforced by AST.

Permitted: stdlib, paios.assistant itself, and the optional SDKs —
'anthropic' only inside adapters/anthropic.py, 'openai' only inside
adapters/openai.py. Everything else — and, above all, ANY other
paios.* module — is forbidden: no repositories, no scheduler, no
runtime, no decision engine, no learning, no daemon, no application,
no persistence modules, no open() calls.
"""

import ast
import sys
from pathlib import Path

import paios.assistant as package

SDK_ALLOWANCES = {
    "anthropic.py": {"anthropic"},
    "openai.py": {"openai"},
}
#: The Ollama adapter's "SDK" is plain local HTTP — urllib is its
#: declared transport, permitted in that one file exactly like the
#: cloud SDKs are in theirs.
TRANSPORT_ALLOWANCES = {
    "ollama.py": {"urllib", "urllib.request", "urllib.error"},
}
FORBIDDEN_STDLIB = {
    "pathlib", "sqlite3", "shelve", "pickle", "dbm", "json.tool",
    "subprocess", "socket", "urllib",
}


def _modules():
    root = Path(package.__file__).parent
    return sorted(root.rglob("*.py"))


def _imports(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            yield node.module or ""


class TestDependencyGraph:
    def test_only_stdlib_own_package_and_declared_sdks(self):
        for module_path in _modules():
            tree = ast.parse(module_path.read_text(encoding="utf-8"))
            allowed_sdks = SDK_ALLOWANCES.get(module_path.name, set())
            for name in _imports(tree):
                top = name.split(".")[0]
                if top == "paios":
                    assert name.startswith("paios.assistant"), (
                        f"{module_path.name} imports {name!r} — the "
                        "assistant may not know the rest of PAIOS"
                    )
                elif top in ("anthropic", "openai"):
                    assert top in allowed_sdks, (
                        f"{module_path.name} imports SDK {name!r} outside "
                        "its adapter"
                    )
                else:
                    assert top in sys.stdlib_module_names, (
                        f"{module_path.name} imports unexpected {name!r}"
                    )
                transport = TRANSPORT_ALLOWANCES.get(
                    module_path.name, set()
                )
                if name in transport or top in transport:
                    continue
                assert name not in FORBIDDEN_STDLIB and top not in (
                    FORBIDDEN_STDLIB
                ), f"{module_path.name} imports forbidden {name!r}"

    def test_no_persistence_no_files(self):
        for module_path in _modules():
            tree = ast.parse(module_path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    assert getattr(node.func, "id", "") != "open", (
                        f"{module_path.name} calls open() — the assistant "
                        "persists nothing"
                    )

    def test_result_dtos_are_frozen(self):
        import dataclasses

        from paios.assistant import AssistantRequest, AssistantResult
        from paios.assistant.response_parser import ParsedResponse
        from paios.assistant.tools import SnapshotComparison

        for dto in (
            AssistantRequest,
            AssistantResult,
            ParsedResponse,
            SnapshotComparison,
        ):
            assert dataclasses.fields(dto)  # is a dataclass
            assert dto.__dataclass_params__.frozen, f"{dto.__name__} not frozen"

    def test_prompt_templates_are_frozen(self):
        from paios.assistant.prompts import EXPLAIN

        import pytest

        with pytest.raises(AttributeError):
            EXPLAIN.system = "rewritten"
