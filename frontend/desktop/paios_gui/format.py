"""Tiny display formatters over REST payload values (strings in/out)."""


def clock(iso: str | None) -> str:
    """'2026-07-21T09:05:00' -> '09:05'."""
    if not iso:
        return "—"
    time_part = iso.split("T")[1] if "T" in iso else iso
    return time_part[:5]


def day_time(iso: str | None) -> str:
    """'2026-07-21T09:05:00' -> '2026-07-21 09:05'."""
    if not iso:
        return "—"
    return iso.replace("T", " ")[:16]


def minutes(value) -> str:
    return f"{int(value)} min" if value is not None else "—"


def percent(value) -> str:
    return f"{value:.0f}%" if value is not None else "—"


def text_or_dash(value) -> str:
    return str(value) if value not in (None, "") else "—"
