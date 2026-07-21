"""PAIOS Desktop Dashboard — a Qt (PySide6) presentation layer.

Milestone 13. The GUI talks to PAIOS exclusively through the REST API
(Milestone 12); it imports nothing from the paios backend packages —
no runtime, no scheduler, no decision engine, no learning, no
repositories, no JSON files. Every screen is built from REST responses
and every action calls exactly one REST endpoint.

Framework: PySide6 (Qt Widgets). Of the mission's preferred order —
Tauri, Qt, Electron — Tauri requires a Rust + Node toolchain and
Electron a Node runtime with a bundled Chromium; neither toolchain
exists in this environment and both would bolt a second language onto a
pure-Python repository. Qt Widgets are native (no embedded browser),
light on memory, and keep the whole system one language.
"""

from paios_gui.client import ApiClient, ApiResponseError, ApiUnreachable
from paios_gui.config import GuiConfig

__all__ = ["ApiClient", "ApiResponseError", "ApiUnreachable", "GuiConfig"]
