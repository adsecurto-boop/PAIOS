"""Dark theme: Fusion style + palette + a small stylesheet.

Dark is the mission's mode and the only one shipped. No animations —
styling is static colors and spacing only.
"""

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

BACKGROUND = "#14161a"
SURFACE = "#1d2026"
SURFACE_ALT = "#23272e"
BORDER = "#32363e"
TEXT = "#d7dae0"
TEXT_DIM = "#8b919c"
ACCENT = "#4c9be8"
GOOD = "#5fb26a"
WARN = "#d9a441"
BAD = "#d96b6b"

STYLESHEET = f"""
QMainWindow, QDialog {{ background: {BACKGROUND}; }}
QWidget {{ color: {TEXT}; font-size: 13px; }}
QWizard, QWizardPage {{ background: {BACKGROUND}; }}
QWizard QLabel {{ color: {TEXT}; }}
QFrame#section {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 4px;
}}
QLabel#sectionTitle {{
    color: {TEXT_DIM};
    font-weight: bold;
    letter-spacing: 1px;
}}
QLabel#banner {{
    background: {BAD};
    color: #14161a;
    font-weight: bold;
    padding: 6px;
    border-radius: 3px;
}}
QLabel#todayHeader {{
    font-size: 18px;
    font-weight: bold;
    letter-spacing: 2px;
}}
QListWidget#navigation {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    outline: none;
}}
QListWidget#navigation::item {{ padding: 7px 10px; }}
QListWidget#navigation::item:selected {{
    background: {SURFACE_ALT};
    color: {ACCENT};
    border-left: 2px solid {ACCENT};
}}
QPushButton {{
    background: {SURFACE_ALT};
    border: 1px solid {BORDER};
    border-radius: 3px;
    padding: 4px 12px;
}}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:disabled {{ color: {TEXT_DIM}; }}
QTableWidget {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    gridline-color: {BORDER};
}}
QHeaderView::section {{
    background: {SURFACE_ALT};
    color: {TEXT_DIM};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 4px;
}}
QLineEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {SURFACE_ALT};
    border: 1px solid {BORDER};
    border-radius: 3px;
    padding: 3px 6px;
}}
QScrollArea {{ border: none; }}
QStatusBar {{ color: {TEXT_DIM}; }}
QFrame#card {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 6px;
}}
QFrame#card:hover {{ border-color: {ACCENT}; }}
QFrame#nowCard {{
    background: {SURFACE_ALT};
    border: 1px solid {ACCENT};
    border-radius: 6px;
}}
QLabel#statusChip {{
    border-radius: 8px;
    padding: 1px 8px;
    font-weight: bold;
}}
QLabel#cardTitle {{ font-size: 14px; font-weight: bold; }}
QLabel#cardWhy {{ color: {TEXT_DIM}; font-style: italic; }}
QLabel#subtitle {{ color: {TEXT_DIM}; }}
QLabel#working {{ color: {WARN}; font-weight: bold; }}
QPlainTextEdit#captureBox {{ font-size: 15px; }}
QPushButton#primaryAction {{
    background: {ACCENT};
    color: {BACKGROUND};
    font-weight: bold;
    padding: 6px 22px;
}}
QPushButton#primaryAction:hover {{ background: #6db0f0; }}
"""

#: Status -> chip color (presentation of server-decided states only).
STATUS_COLORS = {
    "Started": GOOD,
    "Resumed": GOOD,
    "Ready": ACCENT,
    "Paused": WARN,
    "Created": TEXT_DIM,
    "Planned": TEXT_DIM,
    "Completed": GOOD,
    "Cancelled": BAD,
    "Archived": TEXT_DIM,
    "Rejected": BAD,
    "Expired": BAD,
}


def status_color(status: str) -> str:
    return STATUS_COLORS.get(status, TEXT_DIM)


def apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BACKGROUND))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(SURFACE))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(SURFACE_ALT))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor(SURFACE_ALT))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(BACKGROUND))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(SURFACE_ALT))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(TEXT_DIM))
    app.setPalette(palette)
    app.setStyleSheet(STYLESHEET)
