"""The first-run wizard (M20): shown once, answers land in the JSON
settings file (settings_store), and ``first_run_complete`` marks it done.

Pages: backend URL (with a live Test connection against GET /status),
refresh interval, work hours (stored for future use — nothing consumes
them yet), desktop notifications toggle, the AI provider as reported by
GET /assistant/status (read-only — the provider is configured
server-side), and theme (dark is the shipped default).

Skipping rules (app.py enforces them): an existing marker, the
--no-wizard flag (always wins — tests rely on it), or an offscreen Qt
platform unless a test opts in explicitly.
"""

import os

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from paios_gui.client import ApiClient
from paios_gui.config import (
    DEFAULT_BASE_URL,
    DEFAULT_REFRESH_SECONDS,
    MAX_REFRESH_SECONDS,
    MIN_REFRESH_SECONDS,
)


def should_show_wizard(
    settings: dict,
    no_wizard: bool = False,
    environ: dict | None = None,
    force: bool = False,
) -> bool:
    """The one skip decision, testable without a QApplication.

    --no-wizard ALWAYS skips; a stored marker skips; offscreen Qt skips
    unless a test opts in with force=True."""
    if no_wizard:
        return False
    if settings.get("first_run_complete"):
        return False
    env = environ if environ is not None else os.environ
    if env.get("QT_QPA_PLATFORM") == "offscreen" and not force:
        return False
    return True


class _UrlPage(QWizardPage):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.setTitle("Backend connection")
        self.setSubTitle("Where is the PAIOS REST API listening?")
        form = QFormLayout(self)
        self.url_edit = QLineEdit(base_url)
        form.addRow("Backend URL", self.url_edit)
        row = QHBoxLayout()
        test_button = QPushButton("Test connection")
        test_button.clicked.connect(self.test_connection)
        row.addWidget(test_button)
        self.result_label = QLabel("")
        row.addWidget(self.result_label, stretch=1)
        form.addRow(row)

    def test_connection(self) -> None:
        client = ApiClient(self.url_edit.text().strip(), timeout=2.0)
        try:
            status = client.get_status()
        except Exception:
            self.result_label.setText(
                "✗ Could not connect. Check that the PAIOS backend is"
                " running at this address, then try again."
            )
            self.result_label.setWordWrap(True)
            return
        operational = status.get("operational")
        self.result_label.setText(
            "✓ Connected — backend is running"
            if operational
            else "✓ Connected — backend is starting up"
        )


class _PreferencesPage(QWizardPage):
    def __init__(self, refresh_seconds: int) -> None:
        super().__init__()
        self.setTitle("Preferences")
        self.setSubTitle("Polling, work hours and notifications.")
        form = QFormLayout(self)
        self.interval = QSpinBox()
        self.interval.setRange(MIN_REFRESH_SECONDS, MAX_REFRESH_SECONDS)
        self.interval.setValue(refresh_seconds)
        self.interval.setSuffix(" s")
        form.addRow("Refresh interval", self.interval)
        self.work_start = QTimeEdit()
        self.work_start.setDisplayFormat("HH:mm")
        self.work_start.setTime(self.work_start.time().fromString(
            "09:00", "HH:mm"
        ))
        self.work_end = QTimeEdit()
        self.work_end.setDisplayFormat("HH:mm")
        self.work_end.setTime(self.work_end.time().fromString(
            "17:00", "HH:mm"
        ))
        form.addRow("Work hours start", self.work_start)
        form.addRow("Work hours end", self.work_end)
        self.notifications = QCheckBox("Show desktop notifications")
        self.notifications.setChecked(True)
        form.addRow(self.notifications)


class _IntelligencePage(QWizardPage):
    """Choose your PAIOS Intelligence Mode.

    Three modes, all safe: Local AI (free, private, offline via
    Ollama), Cloud AI (user's own key), Basic (the deterministic
    engine that always works). Every action here is optional — the
    wizard never blocks on AI, and skipping the page leaves PAIOS in
    Basic mode."""

    def __init__(self, wizard: "FirstRunWizard") -> None:
        super().__init__()
        self._wizard = wizard
        self._recommended_model: str | None = None
        self.setTitle("Choose your PAIOS Intelligence Mode")
        self.setSubTitle(
            "PAIOS always works — AI is an optional layer on top."
        )
        column = QVBoxLayout(self)

        self.local_radio = QRadioButton("Local AI (Recommended)")
        self.local_radio.setChecked(True)
        column.addWidget(self.local_radio)
        local_text = QLabel(
            "Free. Private. Runs on your computer. Works offline"
            " after setup."
        )
        local_text.setObjectName("subtitle")
        local_text.setWordWrap(True)
        column.addWidget(local_text)
        self.hardware_label = QLabel("Detecting hardware…")
        self.hardware_label.setWordWrap(True)
        column.addWidget(self.hardware_label)
        local_row = QHBoxLayout()
        self.install_button = QPushButton("Install recommended model")
        self.install_button.clicked.connect(self.install_model)
        local_row.addWidget(self.install_button)
        self.use_local_button = QPushButton("Use local AI")
        self.use_local_button.clicked.connect(self.use_local)
        local_row.addWidget(self.use_local_button)
        local_row.addStretch(1)
        column.addLayout(local_row)

        self.cloud_radio = QRadioButton("Cloud AI")
        column.addWidget(self.cloud_radio)
        cloud_text = QLabel(
            "OpenAI or Anthropic Claude with your own API key. The key"
            " is stored encrypted for your Windows account only."
        )
        cloud_text.setObjectName("subtitle")
        cloud_text.setWordWrap(True)
        column.addWidget(cloud_text)
        cloud_row = QHBoxLayout()
        self.cloud_provider = QComboBox()
        self.cloud_provider.addItems(["anthropic", "openai"])
        cloud_row.addWidget(self.cloud_provider)
        self.cloud_key = QLineEdit()
        self.cloud_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.cloud_key.setPlaceholderText("API key (never shared)")
        cloud_row.addWidget(self.cloud_key, stretch=1)
        self.use_cloud_button = QPushButton("Save cloud AI")
        self.use_cloud_button.clicked.connect(self.use_cloud)
        cloud_row.addWidget(self.use_cloud_button)
        column.addLayout(cloud_row)

        self.basic_radio = QRadioButton("Basic Mode")
        column.addWidget(self.basic_radio)
        basic_text = QLabel(
            "No AI. PAIOS plans deterministically — private, instant,"
            " and always available. You can turn AI on later in"
            " Settings."
        )
        basic_text.setObjectName("subtitle")
        basic_text.setWordWrap(True)
        column.addWidget(basic_text)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        column.addWidget(self.status_label)
        column.addStretch(1)

    # --- backend calls (all optional; failures inform, never block) ------

    def _client(self) -> ApiClient:
        return ApiClient(self._wizard.chosen_url(), timeout=4.0)

    def initializePage(self) -> None:  # Qt naming
        try:
            setup = self._client().assistant_setup()
        except Exception:
            self.hardware_label.setText(
                "Backend not reachable — hardware detection and model"
                " installation will be available from Settings once"
                " PAIOS is running. You can finish setup now."
            )
            self.install_button.setEnabled(False)
            self.use_local_button.setEnabled(False)
            self.use_cloud_button.setEnabled(False)
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
        self.hardware_label.setText(
            f"Detected: {profile.get('ram_gb', '?')} GB RAM,"
            f" {profile.get('cpu_cores', '?')} CPU cores"
            + (f", {gpu}" if gpu else "")
            + (
                f".\nRecommended model: {recommended.get('label')}"
                f" ({recommended.get('name')})"
                if recommended
                else ""
            )
        )
        ollama = setup.get("ollama") or {}
        if not ollama.get("server_running"):
            self.status_label.setText(
                "Ollama is not installed yet. Get it free from"
                " https://ollama.com/download — then come back (or use"
                " Settings later) to install the model."
            )
            self.install_button.setEnabled(False)
        elif any(
            m.get("name") == self._recommended_model
            for m in ollama.get("models") or []
        ):
            self.status_label.setText(
                "The recommended model is already installed — click"
                " 'Use local AI' to turn it on."
            )

    def install_model(self) -> None:
        if not self._recommended_model:
            return
        try:
            result = self._client().assistant_ollama_pull(
                self._recommended_model
            )
        except Exception as error:
            self.status_label.setText(f"Could not start download: {error}")
            return
        if result.get("started"):
            self.status_label.setText(
                f"Downloading {self._recommended_model} in the"
                " background (a few GB — this can take a while). You"
                " can finish setup; when the download completes, click"
                " 'Use local AI' here or in Settings."
            )
        else:
            self.status_label.setText(
                result.get("reason") or "Download did not start."
            )

    def use_local(self) -> None:
        try:
            status = self._client().set_assistant_config(
                "ollama", model=self._recommended_model
            )
        except Exception as error:
            self.status_label.setText(f"Could not apply: {error}")
            return
        if status.get("available"):
            self.status_label.setText(
                "Local AI is ready — PAIOS is now using"
                f" {self._recommended_model or 'your local model'}."
            )
        else:
            self.status_label.setText(
                "Saved. Not active yet: "
                + str(status.get("reason") or "")
                + " PAIOS keeps working deterministically meanwhile."
            )

    def use_cloud(self) -> None:
        key = self.cloud_key.text().strip()
        provider = self.cloud_provider.currentText()
        if not key:
            self.status_label.setText(
                "Enter your API key first (it stays on this computer)."
            )
            return
        try:
            status = self._client().set_assistant_config(
                provider, api_key=key
            )
        except Exception as error:
            self.status_label.setText(f"Could not apply: {error}")
            return
        self.cloud_key.clear()
        if status.get("warning"):
            self.status_label.setText(status["warning"])
        elif status.get("available"):
            self.status_label.setText(
                f"Cloud AI ready — PAIOS is now using {provider}."
            )
        else:
            self.status_label.setText(
                "Saved, but the provider is not answering yet: "
                + str(status.get("reason") or "")
            )

    def intelligence_mode(self) -> str:
        if self.local_radio.isChecked():
            return "local"
        if self.cloud_radio.isChecked():
            return "cloud"
        return "basic"


class _StylePage(QWizardPage):
    """Preferred planning style — a GUI preference only, persisted as
    ``planning_style`` in the settings JSON; no backend call."""

    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Preferred planning style")
        self.setSubTitle("How do you like to run your day?")
        column = QVBoxLayout(self)
        self.structured = QRadioButton(
            "Structured day — plan every morning"
        )
        self.flexible = QRadioButton("Flexible list — capture and go")
        self.structured.setChecked(True)
        column.addWidget(self.structured)
        column.addWidget(self.flexible)

    def planning_style(self) -> str:
        return "structured" if self.structured.isChecked() else "flexible"


class _PairPhonePage(QWizardPage):
    """Optional: pair the Android companion right in the first run.
    One button generates the code; skipping is always fine — the
    Mobile page in the app offers the same later."""

    def __init__(self, wizard: "FirstRunWizard") -> None:
        super().__init__()
        self._wizard = wizard
        self.setTitle("Pair your phone (optional)")
        self.setSubTitle(
            "The PAIOS companion app shows your day, captures notes"
            " and talks to your AI — your data stays on this computer."
        )
        column = QVBoxLayout(self)
        steps = QLabel(
            "1. Install the PAIOS companion app on your Android phone."
            "\n2. Make sure phone and computer are on the same Wi-Fi."
            "\n3. Click the button below and enter the code in the"
            " app's Settings → Pair with desktop."
        )
        steps.setWordWrap(True)
        column.addWidget(steps)
        self.generate_button = QPushButton("Generate pairing code")
        self.generate_button.clicked.connect(self.generate)
        row = QHBoxLayout()
        row.addWidget(self.generate_button)
        row.addStretch(1)
        column.addLayout(row)
        self.code_label = QLabel("")
        self.code_label.setObjectName("todayHeader")
        column.addWidget(self.code_label)
        self.status_label = QLabel(
            "You can skip this and pair later from the Mobile page."
        )
        self.status_label.setObjectName("subtitle")
        self.status_label.setWordWrap(True)
        column.addWidget(self.status_label)
        column.addStretch(1)

    def generate(self) -> None:
        client = ApiClient(self._wizard.chosen_url(), timeout=4.0)
        try:
            payload = client.mobile_pairing_start()
        except Exception:
            self.status_label.setText(
                "Could not reach the backend — pair later from the"
                " Mobile page once PAIOS is running."
            )
            return
        self.code_label.setText(str(payload.get("code", "")))
        self.status_label.setText(
            "Enter this code on the phone within 5 minutes. It works"
            " once; generate a new one any time."
        )


class _MorningRoutinePage(QWizardPage):
    """Optional: one click creates the user's first morning routine —
    a daily recurrence the Scheduler expands like any other."""

    DEFAULT_TITLE = "Plan my morning"

    def __init__(self, wizard: "FirstRunWizard") -> None:
        super().__init__()
        self._wizard = wizard
        self.setTitle("Your first morning routine (optional)")
        self.setSubTitle(
            "A small daily anchor: PAIOS schedules it every morning;"
            " open Planning when it fires to shape your day."
        )
        form = QFormLayout(self)
        self.routine_title = QLineEdit(self.DEFAULT_TITLE)
        form.addRow("Routine", self.routine_title)
        self.routine_time = QTimeEdit()
        self.routine_time.setDisplayFormat("HH:mm")
        self.routine_time.setTime(
            self.routine_time.time().fromString("08:30", "HH:mm")
        )
        form.addRow("Every day at", self.routine_time)
        self.create_button = QPushButton("Create routine")
        self.create_button.clicked.connect(self.create_routine)
        form.addRow(self.create_button)
        self.status_label = QLabel(
            "Skip if you prefer — routines live under Planning."
        )
        self.status_label.setObjectName("subtitle")
        self.status_label.setWordWrap(True)
        form.addRow(self.status_label)

    def create_routine(self) -> None:
        client = ApiClient(self._wizard.chosen_url(), timeout=4.0)
        title = self.routine_title.text().strip() or self.DEFAULT_TITLE
        try:
            client.create_recurrence(
                title,
                self.routine_time.time().toString("HH:mm"),
                ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                category="recurring",
            )
        except Exception as error:
            self.status_label.setText(
                f"Could not create it now ({error}) — add it later"
                " under Planning → recurrences."
            )
            return
        self.create_button.setEnabled(False)
        self.status_label.setText(
            f"Done — '{title}' will appear on your plan every day at "
            f"{self.routine_time.time().toString('HH:mm')}."
        )


class _ThemePage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Theme")
        self.setSubTitle("Dark is the shipped default.")
        form = QFormLayout(self)
        self.theme_box = QComboBox()
        self.theme_box.addItems(["dark"])
        form.addRow("Theme", self.theme_box)


class FirstRunWizard(QWizard):
    """Collects the settings dict; the caller persists it."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        refresh_seconds: int = DEFAULT_REFRESH_SECONDS,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("PAIOS — First run")
        # Windows defaults to the native AeroStyle, which paints its own
        # white chrome and ignores the app's dark palette — light-gray
        # text on white made the wizard unreadable on first launch.
        # ClassicStyle renders with the application palette/stylesheet.
        self.setWizardStyle(QWizard.WizardStyle.ClassicStyle)
        self.url_page = _UrlPage(base_url)
        self.preferences_page = _PreferencesPage(refresh_seconds)
        self.style_page = _StylePage()
        self.provider_page = _IntelligencePage(self)
        self.pair_page = _PairPhonePage(self)
        self.routine_page = _MorningRoutinePage(self)
        self.theme_page = _ThemePage()
        # The non-developer path: connect -> preferences -> style ->
        # Setup AI -> Pair phone -> first morning routine -> theme.
        for page in (
            self.url_page,
            self.preferences_page,
            self.style_page,
            self.provider_page,
            self.pair_page,
            self.routine_page,
            self.theme_page,
        ):
            self.addPage(page)

    def chosen_url(self) -> str:
        return self.url_page.url_edit.text().strip() or DEFAULT_BASE_URL

    def settings(self) -> dict:
        """The JSON payload for settings_store.save_settings."""
        preferences = self.preferences_page
        return {
            "base_url": self.chosen_url(),
            "refresh_seconds": preferences.interval.value(),
            "work_hours_start": preferences.work_start.time().toString(
                "HH:mm"
            ),
            "work_hours_end": preferences.work_end.time().toString("HH:mm"),
            "notifications_enabled": preferences.notifications.isChecked(),
            "planning_style": self.style_page.planning_style(),
            "intelligence_mode": self.provider_page.intelligence_mode(),
            "theme": self.theme_page.theme_box.currentText(),
            "first_run_complete": True,
        }
