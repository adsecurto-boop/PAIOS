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


class _ProviderPage(QWizardPage):
    def __init__(self, wizard: "FirstRunWizard") -> None:
        super().__init__()
        self._wizard = wizard
        self.setTitle("AI assistant")
        self.setSubTitle(
            "The provider is configured server-side; this is what the"
            " backend reports."
        )
        form = QFormLayout(self)
        self.provider_label = QLabel("(not queried yet)")
        form.addRow("Provider", self.provider_label)
        self.available_label = QLabel("—")
        form.addRow("Available", self.available_label)
        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        self.summary_label.setObjectName("subtitle")
        form.addRow(self.summary_label)

    def initializePage(self) -> None:  # Qt naming
        client = ApiClient(self._wizard.chosen_url(), timeout=2.0)
        try:
            status = client.assistant_status()
        except Exception:
            self.provider_label.setText("(backend unreachable)")
            self.available_label.setText("—")
            self.summary_label.setText(
                "Could not reach the backend, so the AI provider is"
                " unknown. You can finish setup now — PAIOS will check"
                " again once the backend is running."
            )
            return
        provider = str(status.get("provider", "none"))
        self.provider_label.setText(provider)
        if status.get("available"):
            self.available_label.setText("yes")
            self.summary_label.setText(
                f"Backend connected. AI provider: {provider} — AI-assisted"
                " planning is ready."
            )
            return
        self.available_label.setText("no")
        reason = status.get("reason")
        message = (
            f"Backend connected. AI provider: {provider}. PAIOS will use"
            " deterministic planning until an AI provider is configured"
            " on the backend — everything still works."
        )
        if reason:
            message += f"\n\nDetails: {reason}"
        self.summary_label.setText(message)


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
        self.provider_page = _ProviderPage(self)
        self.theme_page = _ThemePage()
        for page in (
            self.url_page,
            self.preferences_page,
            self.style_page,
            self.provider_page,
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
            "theme": self.theme_page.theme_box.currentText(),
            "first_run_complete": True,
        }
