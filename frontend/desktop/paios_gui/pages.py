"""Navigation pages: read-only tables over list endpoints, plus the
page-local actions the mission requires. Each page's ``refresh(client)``
issues its GET calls; each toolbar button issues exactly one REST call
through the window's ``run_action``."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from paios_gui import format as fmt
from paios_gui.config import MAX_REFRESH_SECONDS, MIN_REFRESH_SECONDS
from paios_gui.dialogs import (
    NameDescriptionDialog,
    OutcomeDialog,
    ProgressDialog,
    ReasonDialog,
    ReflectionDialog,
)

#: Event states shown on the History page (terminal states — the same
#: canonical state names the TUI groups by).
_HISTORY_STATES = ("Completed", "Cancelled", "Archived", "Rejected", "Expired")


class TablePage(QWidget):
    """A titled table + toolbar; subclasses define columns and rows."""

    title = ""
    columns: tuple[str, ...] = ()

    def __init__(self, window) -> None:
        super().__init__()
        self._window = window
        self._rows: list[dict] = []
        layout = QVBoxLayout(self)
        heading = QLabel(self.title.upper())
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        self.toolbar = QHBoxLayout()
        layout.addLayout(self.toolbar)
        self.table = QTableWidget(0, len(self.columns))
        self.table.setHorizontalHeaderLabels(list(self.columns))
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)
        self._build_toolbar()
        self.toolbar.addStretch(1)

    def _build_toolbar(self) -> None:
        """Subclasses add their action buttons here."""

    def _add_button(self, label: str, handler) -> QPushButton:
        button = QPushButton(label)
        button.clicked.connect(handler)
        self.toolbar.addWidget(button)
        return button

    # --- data ------------------------------------------------------------

    def refresh(self, client) -> None:
        self._rows = self.fetch(client)
        self.table.setRowCount(len(self._rows))
        for row_index, row in enumerate(self._rows):
            for column_index, value in enumerate(self.cells(row)):
                item = QTableWidgetItem(value)
                item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )
                self.table.setItem(row_index, column_index, item)

    def fetch(self, client) -> list[dict]:
        raise NotImplementedError

    def cells(self, row: dict) -> tuple[str, ...]:
        raise NotImplementedError

    def selected_row(self) -> dict | None:
        index = self.table.currentRow()
        if 0 <= index < len(self._rows):
            return self._rows[index]
        return None

    def _require_selection(self) -> dict | None:
        row = self.selected_row()
        if row is None:
            self._window.notify("Select a row first.", "warn")
        return row


class GoalsPage(TablePage):
    title = "Goals"
    columns = ("Name", "Status", "Suggested by", "Accepted", "Description")

    def _build_toolbar(self) -> None:
        self._add_button("New goal…", self._on_new)

    def fetch(self, client):
        return client.get_goals()

    def cells(self, row):
        return (
            row["name"],
            row["status"],
            row["suggested_by"],
            fmt.day_time(row["accepted_at"]),
            row["description"],
        )

    def _on_new(self) -> None:
        dialog = NameDescriptionDialog("New goal", self)
        if dialog.exec():
            values = dialog.values()
            self._window.run_action(
                lambda: self._window.client.create_goal(
                    values["name"], values["description"]
                ),
                f"Goal created: {values['name']}",
            )


class ProjectsPage(TablePage):
    title = "Projects"
    columns = ("Name", "Status", "Progress", "Velocity", "Created")

    def _build_toolbar(self) -> None:
        self._add_button("New project…", self._on_new)
        self._add_button("Update progress…", self._on_progress)

    def fetch(self, client):
        return client.get_projects()

    def cells(self, row):
        progress = row.get("progress") or {}
        return (
            row["name"],
            row["status"],
            fmt.percent(progress.get("completion_percentage")),
            fmt.text_or_dash(progress.get("velocity")),
            fmt.day_time(row["created_at"]),
        )

    def _on_new(self) -> None:
        dialog = NameDescriptionDialog("New project", self)
        if dialog.exec():
            values = dialog.values()
            self._window.run_action(
                lambda: self._window.client.create_project(
                    values["name"], values["description"]
                ),
                f"Project created: {values['name']}",
            )

    def _on_progress(self) -> None:
        row = self._require_selection()
        if row is None:
            return
        current = (row.get("progress") or {}).get("completion_percentage", 0.0)
        dialog = ProgressDialog(row["name"], current or 0.0, self)
        if dialog.exec():
            percentage = dialog.values()["completion_percentage"]
            self._window.run_action(
                lambda: self._window.client.update_progress(
                    row["project_id"], percentage
                ),
                f"Progress updated: {row['name']} -> {percentage:.0f}%",
            )


class EventsPage(TablePage):
    title = "Events"
    columns = ("Description", "Category", "Status", "Start", "Duration")

    def _build_toolbar(self) -> None:
        self._add_button("Start", self._simple("start_event", "Event started"))
        self._add_button("Pause", self._simple("pause_event", "Event paused"))
        self._add_button(
            "Resume", self._simple("resume_event", "Event resumed")
        )
        self._add_button("Complete…", self._on_complete)
        self._add_button("Cancel…", self._on_cancel)
        self._add_button("Reflect…", self._on_reflect)

    def fetch(self, client):
        return client.get_events()

    def cells(self, row):
        return (
            row["description"],
            fmt.text_or_dash(row["category"]),
            row["status"],
            fmt.day_time(row["start_time"]),
            fmt.minutes(row["duration_minutes"]),
        )

    def _simple(self, method_name: str, notice: str):
        def handler() -> None:
            row = self._require_selection()
            if row is None:
                return
            client_method = getattr(self._window.client, method_name)
            self._window.run_action(
                lambda: client_method(row["event_id"]), notice
            )

        return handler

    def _on_complete(self) -> None:
        row = self._require_selection()
        if row is None:
            return
        dialog = OutcomeDialog(self)
        if dialog.exec():
            outcome = dialog.values()["actual_outcome"]
            self._window.run_action(
                lambda: self._window.client.complete_event(
                    row["event_id"], outcome
                ),
                "Event completed",
            )

    def _on_cancel(self) -> None:
        row = self._require_selection()
        if row is None:
            return
        dialog = ReasonDialog("Cancel event", "Reason (optional)", self)
        if dialog.exec():
            reason = dialog.values()["reason"]
            self._window.run_action(
                lambda: self._window.client.cancel_event(
                    row["event_id"], reason
                ),
                "Event cancelled",
            )

    def _on_reflect(self) -> None:
        row = self._require_selection()
        if row is None:
            return
        dialog = ReflectionDialog(row["description"], self)
        if dialog.exec():
            values = dialog.values()
            self._window.run_action(
                lambda: self._window.client.create_reflection(
                    row["event_id"], **values
                ),
                "Reflection recorded",
            )


class ResourcesPage(TablePage):
    title = "Resources"
    columns = ("Type", "Value", "Unit", "Negative allowed", "Updated")

    def fetch(self, client):
        return client.get_resources()

    def cells(self, row):
        return (
            row["type"],
            f"{row['current_value']:g}",
            row["unit"],
            "yes" if row["negative_allowed"] else "no",
            fmt.day_time(row["last_updated"]),
        )


class KnowledgePage(TablePage):
    title = "Knowledge"
    columns = (
        "Domain", "Topic", "Concept", "Confidence", "Revisions", "Last revision"
    )

    def fetch(self, client):
        return client.get_knowledge()

    def cells(self, row):
        return (
            row["domain"],
            row["topic"],
            row["concept"],
            f"{row['confidence']:.2f}",
            str(row["revision_count"]),
            fmt.day_time(row["last_revision"]),
        )


class LearningPage(TablePage):
    """Reflections table + the learning summary from /dashboard."""

    title = "Learning"
    columns = ("Created", "Lesson learned", "Improvement", "Confidence")

    def __init__(self, window) -> None:
        super().__init__(window)
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.layout().insertWidget(1, self.summary)

    def fetch(self, client):
        learning = client.get_dashboard()["learning"]
        insight = learning.get("latest_insight")
        self.summary.setText(
            f"Last studied: {fmt.day_time(learning['last_studied'])}"
            f"   ·   Revised today: {learning['revised_today']}"
            f"   ·   Latest insight: "
            + (
                f"[{insight['category']}] confidence {insight['confidence']:.2f}"
                if insight
                else "none"
            )
        )
        return client.get_reflections()[::-1]

    def cells(self, row):
        return (
            fmt.day_time(row["created_at"]),
            fmt.text_or_dash(row["lesson_learned"]),
            fmt.text_or_dash(row["improvement"]),
            fmt.text_or_dash(row["confidence"]),
        )


class HistoryPage(TablePage):
    """Terminal-state events with their full transition history."""

    title = "History"
    columns = ("Description", "Status", "Ended", "Outcome", "Transitions")

    def fetch(self, client):
        return [
            event
            for event in client.get_events()
            if event["status"] in _HISTORY_STATES
        ]

    def cells(self, row):
        transitions = " > ".join(
            f"{record['to_state']} {fmt.clock(record['occurred_at'])}"
            for record in row["transitions"]
        )
        return (
            row["description"],
            row["status"],
            fmt.day_time(row["end_time"]),
            fmt.text_or_dash(row["outcome"]),
            transitions,
        )


class SettingsPage(QWidget):
    """Refresh interval (the configurable poll) and connection info."""

    title = "Settings"

    def __init__(self, window) -> None:
        super().__init__()
        self._window = window
        layout = QVBoxLayout(self)
        heading = QLabel("SETTINGS")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)

        row = QHBoxLayout()
        row.addWidget(QLabel("Refresh interval (seconds):"))
        self.interval = QSpinBox()
        self.interval.setRange(MIN_REFRESH_SECONDS, MAX_REFRESH_SECONDS)
        self.interval.setValue(window.config.refresh_seconds)
        self.interval.valueChanged.connect(window.set_refresh_interval)
        row.addWidget(self.interval)
        row.addStretch(1)
        layout.addLayout(row)

        self.server_label = QLabel(f"Server: {window.client.base_url}")
        layout.addWidget(self.server_label)
        layout.addWidget(
            QLabel(
                "Shortcuts: F5 / Ctrl+R refresh · Ctrl+1…Ctrl+9 pages"
                " · Ctrl+Q quit"
            )
        )
        layout.addStretch(1)

    def refresh(self, client) -> None:
        """Settings shows configuration, not server data."""
