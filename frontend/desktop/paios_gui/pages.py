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
    ProgressDialog,
    confirm,
)

#: Event states shown on the History page (terminal states — the same
#: canonical state names the TUI groups by).
_HISTORY_STATES = ("Completed", "Cancelled", "Archived", "Rejected", "Expired")


class TablePage(QWidget):
    """A titled table + toolbar; subclasses define columns and rows.

    Two shared presentation aids (M20): an empty-state hint shown when
    the fetch returns no rows, and a substring filter (the window's
    toolbar search) that hides non-matching rows — display only, the
    fetched data is untouched."""

    title = ""
    columns: tuple[str, ...] = ()
    empty_hint = "Nothing here yet."

    def __init__(self, window) -> None:
        super().__init__()
        self._window = window
        self._rows: list[dict] = []
        self._filter = ""
        layout = QVBoxLayout(self)
        heading = QLabel(self.title.upper())
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        self.toolbar = QHBoxLayout()
        layout.addLayout(self.toolbar)
        self.empty_label = QLabel(self.empty_hint)
        self.empty_label.setWordWrap(True)
        self.empty_label.hide()
        layout.addWidget(self.empty_label)
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
        self.empty_label.setVisible(not self._rows)
        self._apply_row_filter()

    # --- search filter (presentation only) --------------------------------

    def apply_filter(self, text: str) -> None:
        self._filter = text.strip().lower()
        self._apply_row_filter()

    def _apply_row_filter(self) -> None:
        for row_index, row in enumerate(self._rows):
            matches = not self._filter or any(
                self._filter in value.lower() for value in self.cells(row)
            )
            self.table.setRowHidden(row_index, not matches)

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


class NotificationsPage(TablePage):
    """The notification center (M14): history list, unread state, and
    the two maintenance actions. Reads the window's NotificationCenter —
    notifications are GUI presentation state, not a REST resource."""

    title = "Notifications"
    columns = ("", "Time", "Category", "Message")

    def _build_toolbar(self) -> None:
        self._add_button("Mark all read", self._on_mark_read)
        self._add_button("Clear", self._on_clear)

    def fetch(self, client):
        return self._window.notification_center.entries()

    def cells(self, row):
        return (
            "" if row.read else "*",
            row.occurred_at or "—",
            row.category,
            row.message,
        )

    def _on_mark_read(self) -> None:
        self._window.notification_center.mark_all_read()
        self._window.refresh_now()

    def _on_clear(self) -> None:
        self._window.notification_center.clear()
        self._window.refresh_now()



class BackupsPage(TablePage):
    """Backup manager (M20): list archives, create one, restore one.
    Restore only unpacks files — the server adopts them at its next
    start, which the confirm dialog spells out."""

    title = "Backups"
    columns = ("Archive", "Size")
    empty_hint = "No backups yet. Create one with the button above."

    def _build_toolbar(self) -> None:
        self._add_button("Create backup", self._on_create)
        self._add_button("Restore…", self._on_restore)

    def fetch(self, client):
        return client.list_backups()

    def cells(self, row):
        return (row["name"], f"{row['size_bytes']:,} bytes")

    def _on_create(self) -> None:
        self._window.run_action(
            lambda: self._window.client.create_backup(),
            "Backup created",
        )

    def _on_restore(self) -> None:
        row = self._require_selection()
        if row is None:
            return
        if not confirm(
            self,
            "Restore backup",
            f"Restore '{row['name']}'? Restored files load at the next"
            " application start — restart PAIOS afterwards to adopt them.",
        ):
            return
        self._window.run_action(
            lambda: self._window.client.restore_backup(row["name"]),
            f"Backup restored: {row['name']} (restart PAIOS to adopt)",
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
                " · Ctrl+N new event · Ctrl+I inbox capture"
                " · Ctrl+P planning · Ctrl+F search · Ctrl+Q quit"
            )
        )
        layout.addStretch(1)

    def refresh(self, client) -> None:
        """Settings shows configuration, not server data."""
