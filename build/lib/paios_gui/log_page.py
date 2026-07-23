"""The Logs page (M20): a read-only tail of the GUI's own log file.

Reads the newest ``*.log`` in the configured --log-dir (the M16 log
sink — the one file the GUI is sanctioned to write). Pure viewer: no
parsing, no filtering decisions, just the last lines verbatim. Shows a
friendly empty state when no log dir is configured or nothing exists
there yet.
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

#: How many trailing lines the tail shows.
TAIL_LINES = 400


def newest_log(log_dir: str | None) -> Path | None:
    """The most recently modified *.log under log_dir, if any."""
    if not log_dir:
        return None
    directory = Path(log_dir)
    if not directory.is_dir():
        return None
    logs = sorted(
        directory.glob("*.log"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return logs[0] if logs else None


def tail_text(path: Path, lines: int = TAIL_LINES) -> str:
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        return f"Could not read {path.name}: {error}"
    return "\n".join(content.splitlines()[-lines:])


class LogPage(QWidget):
    title = "Logs"

    def __init__(self, window) -> None:
        super().__init__()
        self._window = window
        layout = QVBoxLayout(self)
        heading = QLabel("LOGS")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)

        bar = QHBoxLayout()
        self.file_label = QLabel("")
        bar.addWidget(self.file_label, stretch=1)
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.reload)
        bar.addWidget(refresh_button)
        layout.addLayout(bar)

        self.viewer = QPlainTextEdit()
        self.viewer.setReadOnly(True)
        self.viewer.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.viewer, stretch=1)
        self.reload()

    def refresh(self, client) -> None:
        """Rides the window's poll; the log is local, not REST."""
        self.reload()

    def reload(self) -> None:
        log_dir = getattr(self._window.config, "log_dir", None)
        if not log_dir:
            self.file_label.setText("No log directory configured.")
            self.viewer.setPlainText(
                "Start the GUI with --log-dir <path> to write and view"
                " its structured log here."
            )
            return
        path = newest_log(log_dir)
        if path is None:
            self.file_label.setText(f"No *.log files in {log_dir} yet.")
            self.viewer.setPlainText(
                "The log file appears after the first logged notice."
            )
            return
        self.file_label.setText(str(path))
        self.viewer.setPlainText(tail_text(path))
        scrollbar = self.viewer.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
