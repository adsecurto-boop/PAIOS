"""The Intelligence page (M21, Phase 2): everything about the AI, with
no config files and no environment variables.

One page over the existing /assistant/* endpoints:

    * pick an Intelligence Mode (Automatic, Local AI, OpenAI, Anthropic,
      Offline) — the choice is persisted server-side and applied live;
    * see Ollama detection (installed, running, models) and the machine
      it would run on (RAM, CPU, GPU);
    * one-click "Use Local AI" (installs the recommended model if
      needed, then switches PAIOS to it);
    * a Test AI button that shows the round-trip latency and the reply;
    * a green / yellow / red status light summarising it all.

The page reads through the window's ApiClient and reports every action
inline; it never raises into the poll loop.
"""

import time

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from paios_gui.client import ApiResponseError, ApiUnreachable
from paios_gui.theme import ACCENT, BAD, GOOD, TEXT_DIM, WARN

#: UI label -> provider the backend understands. "Automatic" is a
#: convenience resolved on the client (Local AI when Ollama is up,
#: otherwise the always-available offline engine).
_MODES = (
    ("Automatic", "auto"),
    ("Local AI (Ollama)", "ollama"),
    ("OpenAI", "openai"),
    ("Anthropic", "anthropic"),
    ("Offline (no AI)", "none"),
)
_CLOUD = ("openai", "anthropic")


class IntelligencePage(QWidget):
    """Custom (non-table) page: the AI control room."""

    title = "Intelligence"

    def __init__(self, window) -> None:
        super().__init__()
        self._window = window
        self._recommended_model: str | None = None
        self._ollama_running = False
        self._available = False

        outer = QVBoxLayout(self)
        heading = QLabel("INTELLIGENCE")
        heading.setObjectName("sectionTitle")
        outer.addWidget(heading)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        body = QWidget()
        scroll.setWidget(body)
        column = QVBoxLayout(body)

        # --- status header ------------------------------------------------
        header = QHBoxLayout()
        self.status_chip = QLabel("Checking…")
        self.status_chip.setObjectName("statusChip")
        self._set_light(TEXT_DIM, "Checking…")
        header.addWidget(self.status_chip)
        # GPU/CPU indicator — the compute the local model would use.
        self.hardware_chip = QLabel("")
        self.hardware_chip.setObjectName("statusChip")
        self.hardware_chip.setStyleSheet(f"background:{TEXT_DIM}; color:#14161a;")
        header.addWidget(self.hardware_chip)
        self.status_text = QLabel("")
        self.status_text.setObjectName("subtitle")
        self.status_text.setWordWrap(True)
        header.addWidget(self.status_text, stretch=1)
        column.addLayout(header)

        # --- mode selector ------------------------------------------------
        column.addWidget(self._label("Intelligence mode"))
        mode_row = QHBoxLayout()
        self.mode_combo = QComboBox()
        for text, _ in _MODES:
            self.mode_combo.addItem(text)
        mode_row.addWidget(self.mode_combo, stretch=1)
        self.apply_button = QPushButton("Apply mode")
        self.apply_button.clicked.connect(self._on_apply_mode)
        mode_row.addWidget(self.apply_button)
        column.addLayout(mode_row)

        # Cloud key (shown only for OpenAI / Anthropic).
        self.key_row = QWidget()
        key_layout = QHBoxLayout(self.key_row)
        key_layout.setContentsMargins(0, 0, 0, 0)
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText(
            "API key — stored encrypted for your Windows account only"
        )
        key_layout.addWidget(self.key_edit, stretch=1)
        self.key_row.hide()
        self.mode_combo.currentIndexChanged.connect(self._toggle_key_row)
        column.addWidget(self.key_row)

        # --- local AI card ------------------------------------------------
        self.local_card = self._card("Local AI (Ollama)")
        card_layout = self.local_card.layout()
        self.ollama_label = QLabel("Detecting Ollama…")
        self.ollama_label.setWordWrap(True)
        card_layout.addWidget(self.ollama_label)
        self.hardware_label = QLabel("")
        self.hardware_label.setObjectName("subtitle")
        self.hardware_label.setWordWrap(True)
        card_layout.addWidget(self.hardware_label)
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(200)
        model_row.addWidget(self.model_combo)
        self.use_local_button = QPushButton("Use Local AI")
        self.use_local_button.setObjectName("primaryAction")
        self.use_local_button.clicked.connect(self._on_use_local)
        model_row.addWidget(self.use_local_button)
        self.install_button = QPushButton("Download model")
        self.install_button.clicked.connect(self._on_install_model)
        model_row.addWidget(self.install_button)
        model_row.addStretch(1)
        card_layout.addLayout(model_row)
        self.model_info = QLabel("")
        self.model_info.setObjectName("subtitle")
        self.model_info.setWordWrap(True)
        card_layout.addWidget(self.model_info)
        column.addWidget(self.local_card)

        # --- test card ----------------------------------------------------
        test_card = self._card("Test the assistant")
        test_layout = test_card.layout()
        test_row = QHBoxLayout()
        self.test_button = QPushButton("Test AI")
        self.test_button.clicked.connect(self._on_test)
        test_row.addWidget(self.test_button)
        self.latency_label = QLabel("")
        self.latency_label.setObjectName("statusChip")
        self.latency_label.hide()
        test_row.addWidget(self.latency_label)
        test_row.addStretch(1)
        test_layout.addLayout(test_row)
        self.test_output = QLabel("")
        self.test_output.setWordWrap(True)
        test_layout.addWidget(self.test_output)
        column.addWidget(test_card)

        column.addStretch(1)

    # --- small builders --------------------------------------------------

    def _label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("cardTitle")
        return label

    def _card(self, title: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        heading = QLabel(title)
        heading.setObjectName("cardTitle")
        layout.addWidget(heading)
        return frame

    def _set_light(self, color: str, text: str) -> None:
        self.status_chip.setText(text)
        self.status_chip.setStyleSheet(
            f"background:{color}; color:#14161a;"
        )

    def _toggle_key_row(self) -> None:
        self.key_row.setVisible(self._selected_provider() in _CLOUD)

    def _selected_provider(self) -> str:
        return _MODES[self.mode_combo.currentIndex()][1]

    # --- data ------------------------------------------------------------

    def refresh(self, client) -> None:
        """Fetch config + Ollama + hardware; repaint. Never raises."""
        try:
            config = client.assistant_config()
            ollama = client.assistant_ollama()
        except ApiUnreachable:
            self._set_light(BAD, "Offline")
            self.status_text.setText(
                "The PAIOS server is not reachable — start it on the"
                " Networking page, then come back."
            )
            return
        except ApiResponseError as error:
            self.status_text.setText(f"Server error: {error}")
            return
        self._apply_config(config, ollama, client)

    def _apply_config(self, config: dict, ollama: dict, client) -> None:
        self._available = bool(config.get("available"))
        provider = config.get("provider", "none")
        self._ollama_running = bool(ollama.get("server_running"))
        installed = ollama.get("models") or []

        # Reflect the active provider in the selector (without firing the
        # apply handler): map backend provider back to a UI row.
        self._select_provider_row(provider)
        self._toggle_key_row()

        # Ollama detection line.
        if not ollama.get("cli_installed") and not self._ollama_running:
            self.ollama_label.setText(
                "Ollama is not installed. Get it free from"
                " https://ollama.com/download — PAIOS detects it"
                " automatically once it is running."
            )
        elif not self._ollama_running:
            self.ollama_label.setText(
                "Ollama is installed but not running. Start Ollama and"
                " PAIOS will pick it up."
            )
        else:
            names = ", ".join(m["name"] for m in installed) or "none yet"
            self.ollama_label.setText(
                f"Ollama is running. Installed models: {names}."
            )

        # Hardware + recommended model (cached from /assistant/setup).
        self._load_hardware(client, installed)

        # Model dropdown: installed models first, then the recommended
        # catalog entry so the user can install it in one click.
        self._populate_models(installed)

        self._repaint_light(provider)

    def _load_hardware(self, client, installed: list) -> None:
        try:
            setup = client.assistant_setup()
        except (ApiUnreachable, ApiResponseError):
            return
        profile = setup.get("hardware") or {}
        models = setup.get("recommended_models") or []
        recommended = next(
            (m for m in models if m.get("recommended")), None
        )
        self._recommended_model = (
            recommended.get("name") if recommended else None
        )
        gpu = profile.get("gpu_name")
        vram = profile.get("vram_gb")
        # GPU/CPU indicator chip.
        if gpu:
            label = f"GPU: {gpu}" + (f" ({vram} GB)" if vram else "")
            self.hardware_chip.setStyleSheet(
                f"background:{GOOD}; color:#14161a;"
            )
        else:
            label = f"CPU: {profile.get('cpu_cores', '?')} cores"
            self.hardware_chip.setStyleSheet(
                f"background:{ACCENT}; color:#14161a;"
            )
        self.hardware_chip.setText(label)
        self.hardware_label.setText(
            f"This machine: {profile.get('ram_gb', '?')} GB RAM,"
            f" {profile.get('cpu_cores', '?')} CPU cores"
            + (f", GPU {gpu}" if gpu else ", no discrete GPU")
            + (
                f".  Recommended model: {recommended.get('label')}"
                f" ({recommended.get('name')})."
                if recommended
                else "."
            )
        )
        # Model info: size on disk + live context length for the model.
        chosen = self.model_combo.currentData() or self._recommended_model
        size = next(
            (
                m.get("size_gb")
                for m in installed
                if m.get("name") == chosen
            ),
            None,
        )
        ram = profile.get("ram_gb")
        parts = []
        if chosen:
            parts.append(f"Model: {chosen}")
        if size:
            parts.append(f"on disk ~{size} GB")
        context = self._context_length(client, chosen, installed)
        if context:
            parts.append(f"context {context:,} tokens")
        if ram:
            parts.append(f"system RAM {ram} GB")
        self.model_info.setText("   ·   ".join(parts))

    def _context_length(self, client, model, installed) -> int | None:
        """The model's context window (Ollama /api/show), or None when
        the model is not installed or the server is not answering."""
        if not model or not any(m.get("name") == model for m in installed):
            return None
        try:
            info = client.assistant_ollama_show(model)
        except (ApiUnreachable, ApiResponseError):
            return None
        value = info.get("context_length")
        return value if isinstance(value, int) else None

    def _populate_models(self, installed: list) -> None:
        wanted = self.model_combo.currentData()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        seen = set()
        for model in installed:
            name = model["name"]
            self.model_combo.addItem(f"{name}  (installed)", name)
            seen.add(name)
        if self._recommended_model and self._recommended_model not in seen:
            self.model_combo.addItem(
                f"{self._recommended_model}  (download)",
                self._recommended_model,
            )
        # Restore the previous selection if still present.
        if wanted is not None:
            index = self.model_combo.findData(wanted)
            if index >= 0:
                self.model_combo.setCurrentIndex(index)
        self.model_combo.blockSignals(False)

    def _select_provider_row(self, provider: str) -> None:
        target = provider if provider in {p for _, p in _MODES} else "none"
        for index, (_, value) in enumerate(_MODES):
            if value == target:
                self.mode_combo.blockSignals(True)
                self.mode_combo.setCurrentIndex(index)
                self.mode_combo.blockSignals(False)
                return

    def _repaint_light(self, provider: str) -> None:
        """Green = an AI is answering; yellow = configured but not ready
        (e.g. Ollama up with no model, or a download pending); red = a
        provider is selected but nothing is available. Offline is always
        safe — PAIOS still plans deterministically."""
        if self._available:
            self._set_light(GOOD, "Ready")
            self.status_text.setText(
                f"AI is active ({provider}). PAIOS is using it for"
                " summaries and planning help."
            )
        elif provider in ("none",):
            self._set_light(ACCENT, "Offline mode")
            self.status_text.setText(
                "No AI selected. PAIOS plans deterministically —"
                " private, instant, always available."
            )
        elif provider == "ollama" and self._ollama_running:
            self._set_light(WARN, "Almost ready")
            self.status_text.setText(
                "Ollama is running but the model is not active yet."
                " Pick a model and click Use Local AI."
            )
        else:
            self._set_light(BAD, "Not ready")
            self.status_text.setText(
                f"{provider} is selected but not reachable. Check the"
                " provider, or switch to Offline mode (always works)."
            )

    # --- actions ---------------------------------------------------------

    def _on_apply_mode(self) -> None:
        provider = self._selected_provider()
        if provider == "auto":
            provider = "ollama" if self._ollama_running else "none"
        if provider in _CLOUD:
            key = self.key_edit.text().strip()
            self._call_set(provider, api_key=key or None)
            self.key_edit.clear()
        elif provider == "ollama":
            self._on_use_local()
        else:
            self._call_set(provider)

    def _on_use_local(self) -> None:
        model = self.model_combo.currentData() or self._recommended_model
        installed_names = self._installed_names()
        if model and model not in installed_names:
            # Not downloaded yet — offer to fetch it first.
            self._on_install_model()
            return
        self._call_set("ollama", model=model)

    def _on_install_model(self) -> None:
        model = self.model_combo.currentData() or self._recommended_model
        if not model:
            self._window.notify("No model to download.", "warn")
            return

        def call():
            result = self._window.client.assistant_ollama_pull(model)
            if not result.get("started"):
                raise ApiResponseError(
                    400, "Ollama", result.get("reason", "download failed")
                )

        self._window.run_action(
            call,
            f"Downloading {model} in the background — click Use Local AI"
            " when it finishes.",
        )

    def _call_set(self, provider, model=None, api_key=None) -> None:
        def call():
            result = self._window.client.set_assistant_config(
                provider, model=model, api_key=api_key
            )
            if result.get("warning"):
                self._window.notify(result["warning"], "warn")

        label = {
            "ollama": f"Local AI enabled ({model or 'default model'})",
            "none": "Switched to offline mode",
        }.get(provider, f"{provider} enabled")
        self._window.run_action(call, label)

    def _on_test(self) -> None:
        self.test_button.setEnabled(False)
        self.latency_label.hide()
        started = time.perf_counter()
        try:
            result = self._window.client.assistant_test()
        except ApiUnreachable as error:
            self.test_output.setText(f"Offline: {error}")
            self.test_button.setEnabled(True)
            return
        except ApiResponseError as error:
            self.test_output.setText(f"Server error: {error}")
            self.test_button.setEnabled(True)
            return
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        ok = result.get("ok")
        color = GOOD if ok else BAD
        self.latency_label.setStyleSheet(f"background:{color}; color:#14161a;")
        self.latency_label.setText(f"{elapsed_ms} ms")
        self.latency_label.show()
        source = result.get("source")
        prefix = (
            "Deterministic engine"
            if source == "heuristic"
            else f"Model ({result.get('adapter', 'llm')})"
        )
        self.test_output.setText(f"{prefix}: {result.get('answer', '')}")
        self.test_button.setEnabled(True)

    # --- helpers ---------------------------------------------------------

    def _installed_names(self) -> set:
        names = set()
        for index in range(self.model_combo.count()):
            text = self.model_combo.itemText(index)
            if "(installed)" in text:
                names.add(self.model_combo.itemData(index))
        return names
