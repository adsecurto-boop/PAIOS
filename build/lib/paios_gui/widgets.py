"""Small shared presentation widgets — no data fetching, no decisions."""

import time
from datetime import datetime, timedelta

from PySide6.QtCore import Qt, QTimer
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


class CountdownLabel(QLabel):
    """A live countdown to a target instant — display sugar only.

    Extrapolates from the server time received at the last refresh (a
    1s QTimer re-renders; every data refresh re-anchors), so the label
    ticks between polls without ever reading a clock of authority.
    Shared by the Timeline's "Up next" and Planning's Today's Focus —
    one implementation, two prefixes."""

    def __init__(
        self,
        prefix: str,
        empty_text: str = "",
        zero_text: str = "",
        minutes: bool = False,
        parent=None,
    ) -> None:
        super().__init__(empty_text, parent)
        self._prefix = prefix
        self._empty = empty_text
        self._zero = zero_text
        self._minutes = minutes
        self._target: datetime | None = None
        self._server_now: datetime | None = None
        self._anchor = 0.0  # monotonic second matching _server_now
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update_text)
        self._timer.start(1000)

    def set_target(
        self, target: datetime | None, server_now: datetime | None
    ) -> None:
        self._target = target
        self._server_now = server_now
        self._anchor = time.monotonic()
        self.update_text()

    def update_text(self) -> None:
        if self._target is None or self._server_now is None:
            self.setText(self._empty)
            return
        now = self._server_now + timedelta(
            seconds=time.monotonic() - self._anchor
        )
        remaining = int((self._target - now).total_seconds())
        if remaining <= 0:
            self.setText(self._zero)
            return
        if self._minutes:
            self.setText(
                f"{self._prefix}{-(-remaining // 60)} minute"
                + ("" if remaining <= 60 else "s")
            )
            return
        hours, rest = divmod(remaining, 3600)
        minutes, seconds = divmod(rest, 60)
        self.setText(f"{self._prefix}{hours:d}:{minutes:02d}:{seconds:02d}")


def elapsed_percent(
    started: datetime | None, duration_minutes, now: datetime
) -> int | None:
    """Elapsed share of a running event's planned duration, clamped to
    0..100 — None when the inputs cannot say."""
    if started is None or not duration_minutes:
        return None
    elapsed = (now - started).total_seconds() / 60.0
    return max(0, min(100, int(elapsed * 100 / duration_minutes)))


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
