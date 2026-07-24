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

from paios_gui.client import ApiResponseError, ApiTimeout, ApiUnreachable
from paios_gui.theme import ACCENT, BAD, GOOD, TEXT_DIM, WARN

#: Seconds between full Intelligence refreshes. The page is refreshed by
#: the window's poll timer (every few seconds), but one refresh costs
#: four backend calls, three of which make the backend probe the local
#: Ollama server. At poll cadence that is a permanent load on a server
#: whose domain work is serialized — and it ran on the UI thread. The
#: facts here (installed models, hardware) change on a human timescale.
_REFRESH_INTERVAL_SECONDS = 30.0

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
        #: Monotonic stamp of the last full refresh (0 = never).
        self._last_refresh = 0.0

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

    def refresh(self, client, force: bool = False) -> None:
        """Fetch config + Ollama + hardware; repaint. Never raises.

        Throttled: the window calls this on every poll tick, but one pass
        is four backend calls that probe Ollama. ``force=True`` is the
        user asking (an applied mode, a finished download).
        """
        now = time.monotonic()
        if not force and now - self._last_refresh < _REFRESH_INTERVAL_SECONDS:
            return
        self._last_refresh = now
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
            self._last_refresh = 0.0  # show the new state at once
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
            # The user just changed the provider: the throttle must not
            # hold the status light on the previous answer.
            self._last_refresh = 0.0
            if result.get("warning"):
                self._window.notify(result["warning"], "warn")

        label = {
            "ollama": f"Local AI enabled ({model or 'default model'})",
            "none": "Switched to offline mode",
        }.get(provider, f"{provider} enabled")
        self._window.run_action(call, label)

    def _on_test(self) -> None:
        """Test the whole chain — desktop backend, then provider —
        naming the link that broke.

        Two calls, not one: the backend is probed first (fast), then the
        provider (slow, with the AI deadline). Before, a single 2 s call
        covered both and every failure read "Offline". Each stage repaints
        before it blocks (``processEvents``), so the user sees "Connecting
        …" and "Asking the AI…" rather than a frozen button. The provider
        call is a deliberate, user-initiated wait — the poll loop that
        must stay responsive never runs this path.
        """
        self.test_button.setEnabled(False)
        self.latency_label.hide()
        client = self._window.client
        started = time.perf_counter()
        try:
            self._stage("Testing the PAIOS backend…")
            client.get_status()
            self._stage("Backend is up. Asking the AI to answer"
                        " (the first reply can take a minute)…")
            result = client.assistant_test()
        except (ApiUnreachable, ApiResponseError) as error:
            self._show_latency(self._elapsed_ms(started), BAD)
            self.test_output.setText(self.explain_failure(error))
            self.test_button.setEnabled(True)
            return
        self._show_test_result(result, self._elapsed_ms(started))
        self.test_button.setEnabled(True)

    def _stage(self, message: str) -> None:
        """Show a step and paint it before the next blocking call.

        A targeted repaint(), not processEvents(): it redraws this label
        synchronously without re-entering the event loop, so it cannot
        flush a deferred widget deletion mid-call."""
        self.test_output.setText(message)
        self.test_output.repaint()

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return int((time.perf_counter() - started) * 1000)

    def _show_test_result(self, result: dict, elapsed_ms: int) -> None:
        ok = bool(result.get("ok"))
        self._show_latency(elapsed_ms, GOOD if ok else BAD)
        source = result.get("source")
        prefix = (
            "Deterministic engine"
            if source == "heuristic"
            else f"Model ({result.get('adapter', 'llm')})"
        )
        answer = result.get("answer", "")
        if ok:
            self.test_output.setText(f"Connected — {prefix}: {answer}")
        else:
            # The backend answered; the PROVIDER did not. Say so, with
            # the provider's own words — never "Offline".
            self.test_output.setText(
                f"Backend is reachable, but the AI did not answer. {answer}"
            )

    @staticmethod
    def explain_failure(error) -> str:
        """The one place a failed AI test becomes words.

        Each branch names a different fact. Collapsing them into
        "Offline" is what made a healthy backend look unreachable.
        """
        if isinstance(error, ApiTimeout):
            return (
                f"The backend accepted the request but sent no answer"
                f" within {error.seconds:g}s. The model is probably still"
                " loading — large models take minutes on the first run."
                " Try again, or pick a smaller model."
            )
        if isinstance(error, ApiUnreachable):
            return (
                f"Could not reach the PAIOS backend: {error}. Start it on"
                " the Networking page, then test again."
            )
        if isinstance(error, ApiResponseError):
            return (
                f"The backend refused the request (HTTP {error.status},"
                f" {error.error_type}): {error}"
            )
        return f"Unexpected failure: {type(error).__name__}: {error}"

    def _show_latency(self, elapsed_ms: int, color: str) -> None:
        self.latency_label.setStyleSheet(f"background:{color}; color:#14161a;")
        self.latency_label.setText(f"{elapsed_ms} ms")
        self.latency_label.show()

    # --- helpers ---------------------------------------------------------

    def _installed_names(self) -> set:
        names = set()
        for index in range(self.model_combo.count()):
            text = self.model_combo.itemText(index)
            if "(installed)" in text:
                names.add(self.model_combo.itemData(index))
        return names
