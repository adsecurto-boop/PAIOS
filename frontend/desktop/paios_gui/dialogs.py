"""Action forms. Each dialog collects fields for exactly one REST call.

Dialogs validate nothing beyond "required field is non-empty" — the API
(and behind it the domain) is the validator; its error message is shown
to the user verbatim. ``values()`` is separated from ``exec()`` so tests
drive forms without an event loop.
"""

from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

#: Enum values mirrored from the REST contract (paios.domain.enums via
#: the API's enum-by-value parsing) — string literals here, not imports.
DISTURBER_TYPES = ("Friend", "Work", "Health", "Environment", "Family", "Other")
DISTURBER_SEVERITIES = ("Low", "Medium", "High")


class _FormDialog(QDialog):
    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        self._form = QFormLayout(self)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self._buttons = buttons

    def _finish(self) -> None:
        self._form.addRow(self._buttons)


class NameDescriptionDialog(_FormDialog):
    """Create Goal / Create Project."""

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(title, parent)
        self.name_edit = QLineEdit()
        self.description_edit = QLineEdit()
        self._form.addRow("Name", self.name_edit)
        self._form.addRow("Description", self.description_edit)
        self._finish()

    def values(self) -> dict:
        return {
            "name": self.name_edit.text().strip(),
            "description": self.description_edit.text().strip(),
        }


class ProgressDialog(_FormDialog):
    """Update Progress on a project."""

    def __init__(self, project_name: str, current: float, parent=None) -> None:
        super().__init__(f"Update progress — {project_name}", parent)
        self.percentage = QDoubleSpinBox()
        self.percentage.setRange(0.0, 100.0)
        self.percentage.setSuffix(" %")
        self.percentage.setValue(current)
        self._form.addRow("Completion", self.percentage)
        self._finish()

    def values(self) -> dict:
        return {"completion_percentage": self.percentage.value()}


class ReasonDialog(_FormDialog):
    """Optional free-text reason (reject recommendation, cancel event)."""

    def __init__(self, title: str, label: str, parent=None) -> None:
        super().__init__(title, parent)
        self.reason_edit = QLineEdit()
        self._form.addRow(label, self.reason_edit)
        self._finish()

    def values(self) -> dict:
        text = self.reason_edit.text().strip()
        return {"reason": text if text else None}


class OutcomeDialog(_FormDialog):
    """Optional actual outcome when completing an event."""

    def __init__(self, parent=None) -> None:
        super().__init__("Complete event", parent)
        self.outcome_edit = QLineEdit()
        self._form.addRow("Actual outcome (optional)", self.outcome_edit)
        self._finish()

    def values(self) -> dict:
        text = self.outcome_edit.text().strip()
        return {"actual_outcome": text if text else None}


class ReflectionDialog(_FormDialog):
    """Create Reflection on a completed event."""

    def __init__(self, event_description: str, parent=None) -> None:
        super().__init__(f"Reflect — {event_description}", parent)
        self.facts = QPlainTextEdit()
        self.interpretation = QPlainTextEdit()
        self.root_cause = QLineEdit()
        self.lesson_learned = QLineEdit()
        self.improvement = QLineEdit()
        self.confidence = QDoubleSpinBox()
        self.confidence.setRange(0.0, 1.0)
        self.confidence.setSingleStep(0.1)
        self.confidence.setValue(0.5)
        for label, field in (
            ("Facts", self.facts),
            ("Interpretation", self.interpretation),
            ("Root cause", self.root_cause),
            ("Lesson learned", self.lesson_learned),
            ("Improvement", self.improvement),
            ("Confidence", self.confidence),
        ):
            self._form.addRow(label, field)
        self._finish()

    def values(self) -> dict:
        def _optional(text: str) -> str | None:
            return text.strip() or None

        return {
            "facts": _optional(self.facts.toPlainText()),
            "interpretation": _optional(self.interpretation.toPlainText()),
            "root_cause": _optional(self.root_cause.text()),
            "lesson_learned": _optional(self.lesson_learned.text()),
            "improvement": _optional(self.improvement.text()),
            "confidence": self.confidence.value(),
        }


class OptionalDateTime(QWidget):
    """Checkbox-gated date+time picker: unchecked means 'not set'."""

    def __init__(self, label: str = "Set", parent=None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.enabled_box = QCheckBox(label)
        self.picker = QDateTimeEdit(QDateTime.currentDateTime())
        self.picker.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.picker.setCalendarPopup(True)
        self.picker.setEnabled(False)
        self.enabled_box.toggled.connect(self.picker.setEnabled)
        row.addWidget(self.enabled_box)
        row.addWidget(self.picker, stretch=1)

    def set_iso(self, iso: str | None) -> None:
        if not iso:
            self.enabled_box.setChecked(False)
            return
        self.enabled_box.setChecked(True)
        self.picker.setDateTime(
            QDateTime.fromString(iso[:16], "yyyy-MM-ddTHH:mm")
        )

    def iso(self) -> str | None:
        if not self.enabled_box.isChecked():
            return None
        return self.picker.dateTime().toString("yyyy-MM-ddTHH:mm:00")


class EventDialog(_FormDialog):
    """Create / edit an Event intent: the POST/PUT /events body.

    Core fields go in the request root; the planning extras (duration,
    energy, tags, deadline, dependencies) form the ``metadata`` block —
    included only when at least one of them is set, so a bare title
    creates a bare intent."""

    ENERGY_LEVELS = ("none", "low", "medium", "high")

    def __init__(self, title: str = "New event", parent=None) -> None:
        super().__init__(title, parent)
        self.title_edit = QLineEdit()
        self.when = OptionalDateTime("Schedule at")
        self.priority = QDoubleSpinBox()
        self.priority.setRange(0.0, 100.0)
        self.priority.setSpecialValueText("(default)")
        self.duration = QSpinBox()
        self.duration.setRange(0, 1440)
        self.duration.setSuffix(" min")
        self.duration.setSpecialValueText("(unset)")
        self.energy = QComboBox()
        self.energy.addItems(self.ENERGY_LEVELS)
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("comma, separated, tags")
        self.deadline = OptionalDateTime("Deadline")
        self.project_edit = QLineEdit()
        self.project_edit.setPlaceholderText("optional project id")
        for label, field in (
            ("Title", self.title_edit),
            ("When", self.when),
            ("Priority", self.priority),
            ("Duration", self.duration),
            ("Energy", self.energy),
            ("Tags", self.tags_edit),
            ("Deadline", self.deadline),
            ("Project", self.project_edit),
        ):
            self._form.addRow(label, field)
        self._finish()

    def prefill(self, event: dict, metadata: dict) -> None:
        """Load the current values for an Edit round-trip."""
        self.title_edit.setText(event.get("description") or "")
        self.when.set_iso(event.get("start_time"))
        if metadata.get("estimated_duration_minutes"):
            self.duration.setValue(
                int(metadata["estimated_duration_minutes"])
            )
        if metadata.get("energy") in self.ENERGY_LEVELS:
            self.energy.setCurrentText(metadata["energy"])
        if metadata.get("tags"):
            self.tags_edit.setText(", ".join(metadata["tags"]))
        self.deadline.set_iso(metadata.get("deadline"))

    def values(self) -> dict:
        metadata: dict = {}
        if self.duration.value() > 0:
            metadata["estimated_duration_minutes"] = self.duration.value()
        if self.energy.currentText() != "none":
            metadata["energy"] = self.energy.currentText()
        tags = [
            tag.strip()
            for tag in self.tags_edit.text().split(",")
            if tag.strip()
        ]
        if tags:
            metadata["tags"] = tags
        if self.deadline.iso() is not None:
            metadata["deadline"] = self.deadline.iso()
        return {
            "title": self.title_edit.text().strip(),
            "suggested_time": self.when.iso(),
            "priority": self.priority.value() or None,
            "project_id": self.project_edit.text().strip() or None,
            "metadata": metadata or None,
        }


class DuplicateDialog(_FormDialog):
    """Duplicate an event, optionally at a new time."""

    def __init__(self, event_description: str, parent=None) -> None:
        super().__init__(f"Duplicate — {event_description}", parent)
        self.when = OptionalDateTime("New time")
        self._form.addRow("When", self.when)
        self._finish()

    def values(self) -> dict:
        return {"suggested_time": self.when.iso()}


class SaveTemplateDialog(_FormDialog):
    """Name prompt for 'Save as template'."""

    def __init__(self, parent=None) -> None:
        super().__init__("Save as template", parent)
        self.name_edit = QLineEdit()
        self._form.addRow("Template name", self.name_edit)
        self._finish()

    def values(self) -> dict:
        return {"name": self.name_edit.text().strip()}


class ConvertInboxDialog(_FormDialog):
    """Convert an inbox capture into a Goal, Project or Event."""

    TARGETS = ("goal", "project", "event")

    def __init__(self, item_text: str, parent=None) -> None:
        super().__init__(f"Convert — {item_text}", parent)
        self.target = QComboBox()
        self.target.addItems(self.TARGETS)
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText(item_text)
        self.when = OptionalDateTime("Schedule at")
        self._form.addRow("Convert to", self.target)
        self._form.addRow("Title (optional)", self.title_edit)
        self._form.addRow("When", self.when)
        self._finish()

    def values(self) -> dict:
        return {
            "to": self.target.currentText(),
            "title": self.title_edit.text().strip() or None,
            "suggested_time": self.when.iso(),
        }


class ShortcutsDialog(QDialog):
    """A discoverable reference of every keyboard shortcut (F1)."""

    SHORTCUTS = (
        ("F5  /  Ctrl+R", "Refresh the current page"),
        ("Ctrl+1 … Ctrl+9", "Jump to a page by position"),
        ("Ctrl+N", "New event"),
        ("Ctrl+I", "Capture to the Inbox"),
        ("Ctrl+P", "Open Planning"),
        ("Ctrl+F", "Search the current table"),
        ("Ctrl+,", "Open Settings"),
        ("F1", "Show this shortcuts list"),
        ("Ctrl+Q", "Quit PAIOS"),
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Keyboard shortcuts")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        heading = QLabel("Keyboard shortcuts")
        heading.setObjectName("cardTitle")
        layout.addWidget(heading)
        table = QTableWidget(len(self.SHORTCUTS), 2)
        table.setHorizontalHeaderLabels(["Shortcut", "Action"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setStretchLastSection(True)
        for row, (keys, action) in enumerate(self.SHORTCUTS):
            table.setItem(row, 0, QTableWidgetItem(keys))
            table.setItem(row, 1, QTableWidgetItem(action))
        table.resizeColumnsToContents()
        layout.addWidget(table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        buttons.button(
            QDialogButtonBox.StandardButton.Close
        ).clicked.connect(self.accept)
        layout.addWidget(buttons)


def confirm(parent, title: str, question: str) -> bool:
    """One shared yes/no gate for every destructive action."""
    return (
        QMessageBox.question(
            parent,
            title,
            question,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        == QMessageBox.StandardButton.Yes
    )


class _ManagerDialog(QDialog):
    """A list-and-act dialog: a table of records plus action buttons.
    Every button performs exactly one REST call via window.run_action."""

    title = ""
    columns: tuple[str, ...] = ()

    def __init__(self, window, parent=None) -> None:
        super().__init__(parent)
        self._window = window
        self._rows: list[dict] = []
        self.setWindowTitle(self.title)
        self.setMinimumSize(560, 360)
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, len(self.columns))
        self.table.setHorizontalHeaderLabels(list(self.columns))
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)
        self.buttons_row = QHBoxLayout()
        layout.addLayout(self.buttons_row)
        self._build_buttons()
        self.buttons_row.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        self.buttons_row.addWidget(close)
        self.reload()

    def _build_buttons(self) -> None:
        """Subclasses add their action buttons here."""

    def _add_button(self, label: str, handler) -> QPushButton:
        button = QPushButton(label)
        button.clicked.connect(handler)
        self.buttons_row.addWidget(button)
        return button

    def reload(self) -> None:
        try:
            self._rows = self.fetch(self._window.client)
        except Exception as error:
            self._window.notify(f"Load failed: {error}", "error")
            self._rows = []
        self.table.setRowCount(len(self._rows))
        for row_index, row in enumerate(self._rows):
            for column_index, value in enumerate(self.cells(row)):
                self.table.setItem(
                    row_index, column_index, QTableWidgetItem(value)
                )

    def fetch(self, client) -> list[dict]:
        raise NotImplementedError

    def cells(self, row: dict) -> tuple[str, ...]:
        raise NotImplementedError

    def selected_row(self) -> dict | None:
        index = self.table.currentRow()
        if 0 <= index < len(self._rows):
            return self._rows[index]
        self._window.notify("Select a row first.", "warn")
        return None


class TemplatesDialog(_ManagerDialog):
    """Event templates: list, instantiate, delete."""

    title = "Templates"
    columns = ("Name", "Title", "Category", "Created")

    def _build_buttons(self) -> None:
        self._add_button("Instantiate…", self._on_instantiate)
        self._add_button("Delete…", self._on_delete)

    def fetch(self, client):
        return client.list_templates()

    def cells(self, row):
        return (
            row["name"],
            row["title"],
            row.get("category") or "—",
            (row.get("created_at") or "—").replace("T", " ")[:16],
        )

    def _on_instantiate(self) -> None:
        row = self.selected_row()
        if row is None:
            return
        dialog = DuplicateDialog(row["name"], self)
        dialog.setWindowTitle(f"Instantiate — {row['name']}")
        if dialog.exec():
            when = dialog.values()["suggested_time"]
            self._window.run_action(
                lambda: self._window.client.instantiate_template(
                    row["id"], suggested_time=when
                ),
                f"Template instantiated: {row['name']}",
            )
            self.reload()

    def _on_delete(self) -> None:
        row = self.selected_row()
        if row is None:
            return
        if not confirm(
            self, "Delete template", f"Delete template '{row['name']}'?"
        ):
            return
        self._window.run_action(
            lambda: self._window.client.delete_template(row["id"]),
            f"Template deleted: {row['name']}",
        )
        self.reload()


class RecurrenceDialog(_FormDialog):
    """Create a recurrence rule: title, HH:MM, weekday checkboxes."""

    DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

    def __init__(self, parent=None) -> None:
        super().__init__("New recurrence", parent)
        self.title_edit = QLineEdit()
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        days_row = QWidget()
        days_layout = QHBoxLayout(days_row)
        days_layout.setContentsMargins(0, 0, 0, 0)
        self.day_boxes: dict[str, QCheckBox] = {}
        for day in self.DAYS:
            box = QCheckBox(day)
            self.day_boxes[day] = box
            days_layout.addWidget(box)
        self._form.addRow("Title", self.title_edit)
        self._form.addRow("Time of day", self.time_edit)
        self._form.addRow("Days", days_row)
        self._finish()

    def values(self) -> dict:
        return {
            "title": self.title_edit.text().strip(),
            "time_of_day": self.time_edit.time().toString("HH:mm"),
            "days": [
                day for day, box in self.day_boxes.items() if box.isChecked()
            ],
        }


class RecurrencesDialog(_ManagerDialog):
    """Recurring event rules: list, create, delete."""

    title = "Recurrences"
    columns = ("Title", "Time", "Days", "Next run", "Enabled")

    def _build_buttons(self) -> None:
        self._add_button("New…", self._on_new)
        self._add_button("Delete…", self._on_delete)

    def fetch(self, client):
        return client.list_recurrences()

    def cells(self, row):
        return (
            row["title"],
            row["time_of_day"],
            " ".join(row.get("days") or ()),
            (row.get("next_run") or "—").replace("T", " ")[:16],
            "yes" if row.get("enabled", True) else "no",
        )

    def _on_new(self) -> None:
        dialog = RecurrenceDialog(self)
        if dialog.exec():
            values = dialog.values()
            self._window.run_action(
                lambda: self._window.client.create_recurrence(**values),
                f"Recurrence created: {values['title']}",
            )
            self.reload()

    def _on_delete(self) -> None:
        row = self.selected_row()
        if row is None:
            return
        if not confirm(
            self, "Delete recurrence", f"Delete recurrence '{row['title']}'?"
        ):
            return
        self._window.run_action(
            lambda: self._window.client.delete_recurrence(row["id"]),
            f"Recurrence deleted: {row['title']}",
        )
        self.reload()


class DisturberDialog(_FormDialog):
    """Report Disturbance."""

    def __init__(self, parent=None) -> None:
        super().__init__("Report disturbance", parent)
        self.type_box = QComboBox()
        self.type_box.addItems(DISTURBER_TYPES)
        self.severity_box = QComboBox()
        self.severity_box.addItems(DISTURBER_SEVERITIES)
        self.description_edit = QLineEdit()
        self._form.addRow("Type", self.type_box)
        self._form.addRow("Severity", self.severity_box)
        self._form.addRow("Description", self.description_edit)
        self._finish()

    def values(self) -> dict:
        return {
            "type": self.type_box.currentText(),
            "severity": self.severity_box.currentText(),
            "description": self.description_edit.text().strip(),
        }
