"""Action forms. Each dialog collects fields for exactly one REST call.

Dialogs validate nothing beyond "required field is non-empty" — the API
(and behind it the domain) is the validator; its error message is shown
to the user verbatim. ``values()`` is separated from ``exec()`` so tests
drive forms without an event loop.
"""

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
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
