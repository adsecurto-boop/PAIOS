"""Small shared presentation widgets — no data fetching, no decisions."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QListWidget,
    QSizePolicy,
    QVBoxLayout,
)

from paios_gui import theme


class Section(QFrame):
    """A titled dashboard card: title row + caller-filled body layout."""

    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("section")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(10, 8, 10, 10)
        self._layout.setSpacing(4)
        heading = QLabel(title.upper())
        heading.setObjectName("sectionTitle")
        self._layout.addWidget(heading)
        self._body: list[QLabel] = []

    @property
    def body_layout(self) -> QVBoxLayout:
        return self._layout

    def set_lines(self, lines: list[str]) -> None:
        """Replace the card's body with plain text lines."""
        for label in self._body:
            self._layout.removeWidget(label)
            # Detach before deleteLater: a deferred-deleted child keeps
            # painting at its old spot until the event loop collects it.
            label.hide()
            label.setParent(None)
            label.deleteLater()
        self._body = []
        for line in lines:
            label = QLabel(line)
            label.setWordWrap(True)
            label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            # Minimum vertical policy: the card may not squash the line
            # below its size hint (grid rows would clip the text).
            label.setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum
            )
            self._body.append(label)
            self._layout.addWidget(label)

    def body_text(self) -> str:
        """The card's current text (test hook and clipboard aid)."""
        return "\n".join(label.text() for label in self._body)


class NoticeLog(QListWidget):
    """The Notifications feed: newest first, presentation state only —
    action results and connection changes the GUI itself observed."""

    MAX_ENTRIES = 50

    def add_notice(self, text: str, kind: str = "info") -> None:
        self.insertItem(0, text)
        color = {
            "info": theme.TEXT_DIM,
            "ok": theme.GOOD,
            "warn": theme.WARN,
            "error": theme.BAD,
        }.get(kind, theme.TEXT_DIM)
        self.item(0).setForeground(QColor(color))
        while self.count() > self.MAX_ENTRIES:
            self.takeItem(self.count() - 1)

    def notices(self) -> list[str]:
        return [self.item(i).text() for i in range(self.count())]
