"""QR codes for the pairing and networking pages (M21).

Presentation only, so it lives in the GUI tier (the backend stays
dependency-free). ``segno`` does the encoding — a pure-Python,
zero-dependency, well-tested library that PyInstaller bundles into the
frozen product like PySide6.

Two renderers over one encoded matrix:

    matrix(text)     -> list[list[bool]]      (testable, no Qt)
    ascii_art(text)  -> str                   (logs / copy / headless)
    pixmap(text)     -> QPixmap               (the on-screen code)
"""


def connection_uri(
    lan_url: str | None = None,
    relay_url: str | None = None,
    account: str = "default",
) -> str:
    """A versioned pairing payload the phone scans: it carries whichever
    endpoints exist so the app can auto-select LAN, then relay, then
    offline. Falls back to the plain LAN URL when there is no relay (a
    generic scanner still shows a usable address)."""
    if relay_url:
        parts = []
        if lan_url:
            parts.append(f"lan={lan_url}")
        parts.append(f"relay={relay_url}")
        parts.append(f"account={account}")
        return "paios://pair?" + "&".join(parts)
    return lan_url or ""


def _qr(text: str):
    import segno

    # Error level M scans reliably from a phone screen photo while
    # keeping short URLs to a small, sharp version.
    return segno.make(text, error="m")


def matrix(text: str) -> list[list[bool]]:
    """The QR modules as rows of booleans (True = dark)."""
    return [[bool(cell) for cell in row] for row in _qr(text).matrix]


def ascii_art(text: str, quiet_zone: int = 2) -> str:
    """A scannable text rendering (two chars per module for aspect),
    with a light quiet zone. Used in logs and as a copy-paste fallback
    where no image can be shown."""
    rows = matrix(text)
    width = len(rows[0]) + quiet_zone * 2
    blank = "  " * width
    lines = [blank] * quiet_zone
    for row in rows:
        cells = "  " * quiet_zone
        cells += "".join("██" if cell else "  " for cell in row)
        cells += "  " * quiet_zone
        lines.append(cells)
    lines.extend([blank] * quiet_zone)
    return "\n".join(lines)


def pixmap(text: str, module_pixels: int = 6, quiet_zone: int = 4):
    """A crisp black-on-white QPixmap of the QR for ``text``.

    Drawn by hand from the module matrix (no temp files, no PNG
    encoder needed): each dark module is a filled square, sized so the
    whole code is a comfortable on-screen target."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPainter, QPixmap

    rows = matrix(text)
    count = len(rows)
    side = (count + quiet_zone * 2) * module_pixels
    image = QPixmap(side, side)
    image.fill(QColor("white"))
    painter = QPainter(image)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("black"))
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            if cell:
                painter.drawRect(
                    (c + quiet_zone) * module_pixels,
                    (r + quiet_zone) * module_pixels,
                    module_pixels,
                    module_pixels,
                )
    painter.end()
    return image
