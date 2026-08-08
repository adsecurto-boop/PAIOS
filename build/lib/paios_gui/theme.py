"""Theme system: refined dark and light palettes (M24).

Dark remains the shipped default; light is a first-class alternative,
switchable at runtime from Settings and persisted. Both share one
stylesheet builder and one semantic status palette, so every page looks
consistent in either mode. Status colours are chosen to read on both a
dark and a light surface (they always pair with dark chip text).

Backward compatibility: the original module constants (BACKGROUND,
SURFACE, ACCENT, GOOD, …) and ``apply_dark_theme`` are preserved, so
existing callers and tests keep working unchanged.
"""

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# --- semantic accent + status colours (shared by both themes) ---------------

ACCENT = "#4c9be8"
GOOD = "#3fa651"
WARN = "#c78a1e"
BAD = "#cf5555"
CHIP_TEXT = "#0f1115"  # dark text used on every coloured chip

# --- palettes ---------------------------------------------------------------

DARK = {
    "bg": "#14161a",
    "surface": "#1d2026",
    "surface_alt": "#23272e",
    "border": "#32363e",
    "text": "#d7dae0",
    "text_dim": "#8b919c",
    "hover": "#6db0f0",
    "selection": "#2b3340",
    # Disabled text. Qt DERIVES this when the palette leaves the Disabled
    # colour group unset, and its derivation is a mid grey chosen without
    # knowing our background — on the first-run wizard, whose Intelligence
    # page disables three buttons whenever the backend is not answering
    # yet, that produced washed-out labels nobody could read. Both values
    # below clear 4.5:1 against their own surface.
    "text_disabled": "#8e949e",
}

LIGHT = {
    "bg": "#f6f7f9",
    "surface": "#ffffff",
    "surface_alt": "#eef0f3",
    "border": "#d8dbe0",
    "text": "#1d2026",
    "text_dim": "#6b7280",
    "hover": "#2f7fd0",
    "selection": "#e3edf9",
    "text_disabled": "#636972",
}

THEMES = {"dark": DARK, "light": LIGHT}
DEFAULT_THEME = "dark"

# --- legacy module constants (the dark palette) -----------------------------
# Kept so existing imports (theme.BACKGROUND, from theme import GOOD, …)
# continue to resolve. New code should prefer the palette dictionaries.
BACKGROUND = DARK["bg"]
SURFACE = DARK["surface"]
SURFACE_ALT = DARK["surface_alt"]
BORDER = DARK["border"]
TEXT = DARK["text"]
TEXT_DIM = DARK["text_dim"]


def build_stylesheet(p: dict) -> str:
    """The application QSS for a palette. Rounded cards, comfortable
    spacing, quiet borders — the same structure in dark and light."""
    return f"""
QMainWindow, QDialog {{ background: {p['bg']}; }}
QWidget {{ color: {p['text']}; font-size: 13px; }}
QWidget:disabled {{ color: {p['text_disabled']}; }}
/* The setup wizard is the first screen a new user ever sees, and on
   Windows QWizard is happy to paint its own light chrome. Pin every
   surface it owns — frame, header band, watermark column — so it can
   never render as light-grey-on-white before the palette settles. */
QWizard, QWizardPage {{ background: {p['bg']}; }}
QWizard > QWidget {{ background: {p['bg']}; }}
QWizard QFrame {{ background: {p['bg']}; }}
QWizard QLabel {{ color: {p['text']}; background: transparent; }}
QWizard QLabel:disabled {{ color: {p['text_disabled']}; }}
QToolTip {{
    background: {p['surface_alt']};
    color: {p['text']};
    border: 1px solid {p['border']};
    padding: 4px 6px;
}}
QFrame#section {{
    background: {p['surface']};
    border: 1px solid {p['border']};
    border-radius: 8px;
}}
QLabel#sectionTitle {{
    color: {p['text_dim']};
    font-weight: bold;
    letter-spacing: 1px;
}}
QLabel#banner {{
    background: {BAD};
    color: {CHIP_TEXT};
    font-weight: bold;
    padding: 7px;
    border-radius: 6px;
}}
QLabel#successBanner {{
    background: {GOOD};
    color: {CHIP_TEXT};
    font-weight: bold;
    padding: 7px;
    border-radius: 6px;
}}
QLabel#todayHeader {{
    font-size: 18px;
    font-weight: bold;
    letter-spacing: 1px;
}}
QListWidget#navigation {{
    background: {p['surface']};
    border: 1px solid {p['border']};
    border-radius: 8px;
    outline: none;
    padding: 4px;
}}
QListWidget#navigation::item {{
    padding: 8px 12px;
    border-radius: 6px;
    margin: 1px 2px;
}}
QListWidget#navigation::item:hover {{ background: {p['surface_alt']}; }}
QListWidget#navigation::item:selected {{
    background: {p['selection']};
    color: {ACCENT};
    font-weight: bold;
}}
QPushButton {{
    background: {p['surface_alt']};
    border: 1px solid {p['border']};
    border-radius: 6px;
    padding: 5px 14px;
}}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:focus {{ border: 1px solid {ACCENT}; }}
QPushButton:disabled {{
    color: {p['text_disabled']};
    background: {p['surface']};
}}
QTableWidget {{
    background: {p['surface']};
    border: 1px solid {p['border']};
    border-radius: 8px;
    gridline-color: {p['border']};
}}
QTableWidget::item:selected {{
    background: {p['selection']};
    color: {p['text']};
}}
QHeaderView::section {{
    background: {p['surface_alt']};
    color: {p['text_dim']};
    border: none;
    border-bottom: 1px solid {p['border']};
    padding: 6px;
}}
QLineEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTimeEdit {{
    background: {p['surface_alt']};
    border: 1px solid {p['border']};
    border-radius: 6px;
    padding: 4px 7px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
    border: 1px solid {ACCENT};
}}
QLineEdit:disabled, QPlainTextEdit:disabled, QSpinBox:disabled,
QDoubleSpinBox:disabled, QComboBox:disabled, QTimeEdit:disabled {{
    color: {p['text_disabled']};
    background: {p['surface']};
}}
QRadioButton:disabled, QCheckBox:disabled {{
    color: {p['text_disabled']};
}}
QScrollArea {{ border: none; }}
QStatusBar {{ color: {p['text_dim']}; }}
QFrame#card {{
    background: {p['surface']};
    border: 1px solid {p['border']};
    border-radius: 10px;
}}
QFrame#card:hover {{ border-color: {ACCENT}; }}
QFrame#nowCard {{
    background: {p['surface_alt']};
    border: 1px solid {ACCENT};
    border-radius: 10px;
}}
QLabel#statusChip {{
    border-radius: 9px;
    padding: 2px 9px;
    font-weight: bold;
}}
QLabel#cardTitle {{ font-size: 14px; font-weight: bold; }}
QLabel#cardWhy {{ color: {p['text_dim']}; font-style: italic; }}
QLabel#subtitle {{ color: {p['text_dim']}; }}
QLabel#working {{ color: {WARN}; font-weight: bold; }}
QPlainTextEdit#captureBox {{ font-size: 15px; }}
QPushButton#primaryAction {{
    background: {ACCENT};
    color: {CHIP_TEXT};
    font-weight: bold;
    border: none;
    padding: 7px 22px;
}}
QPushButton#primaryAction:hover {{ background: {p['hover']}; }}
"""


# The shipped default stylesheet (dark) — kept as a module constant for
# any code or test that references theme.STYLESHEET directly.
STYLESHEET = build_stylesheet(DARK)

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


def normalize_theme(mode: str | None) -> str:
    return mode if mode in THEMES else DEFAULT_THEME


def _qpalette(p: dict) -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(p["bg"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(p["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(p["surface"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(p["surface_alt"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(p["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(p["surface_alt"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(p["text"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(CHIP_TEXT))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(p["surface_alt"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(p["text"]))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(p["text_dim"]))
    # Every colour group, explicitly. An unset group is not "the same as
    # Active" — Qt derives it, and the derived Disabled/Inactive text is
    # a low-contrast grey that made disabled wizard controls unreadable.
    disabled = QColor(p["text_disabled"])
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.PlaceholderText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, disabled)
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Window,
        QColor(p["bg"]),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Base,
        QColor(p["surface"]),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Button,
        QColor(p["surface_alt"]),
    )
    # Inactive (the window does not have focus) must look like Active,
    # not like a third, dimmer theme.
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(
            QPalette.ColorGroup.Inactive, role, QColor(p["text"])
        )
    return palette


def apply_theme(app: QApplication, mode: str = DEFAULT_THEME) -> str:
    """Apply the dark or light theme; returns the normalized mode."""
    mode = normalize_theme(mode)
    palette = THEMES[mode]
    app.setStyle("Fusion")
    app.setPalette(_qpalette(palette))
    app.setStyleSheet(build_stylesheet(palette))
    return mode


def apply_dark_theme(app: QApplication) -> None:
    """Backward-compatible entry point (the shipped default)."""
    apply_theme(app, "dark")
