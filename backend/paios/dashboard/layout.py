"""Frame geometry: banners, section separators, line clipping.

Layout knows widths and section order — never data, never meanings.
"""

TITLE = "PAIOS DASHBOARD"

#: Section order exactly as the mission sketch defines it.
SECTION_ORDER = (
    "CURRENT EVENT",
    "CURRENT CONTEXT",
    "RECOMMENDATIONS",
    "GOALS",
    "PROJECTS",
    "TODAY",
    "HEALTH",
    "LEARNING",
    "SYSTEM",
)


def banner(width: int) -> list[str]:
    return ["=" * width, TITLE.center(width), "=" * width]


def separator(width: int) -> str:
    return "-" * width


def clip(line: str, width: int) -> str:
    """One line never exceeds the frame width (ellipsis when clipped)."""
    if len(line) <= width:
        return line
    if width <= 3:
        return line[:width]
    return line[: width - 3] + "..."


def section(title: str, lines: list[str], width: int) -> list[str]:
    rendered = [separator(width), title, separator(width)]
    rendered.extend(clip(line, width) for line in (lines or ["-"]))
    return rendered


def compose(header_lines: list[str], sections, width: int) -> str:
    """Assemble the full frame: banner, header, then each (title, lines)
    section in the given order. Returns one newline-joined string."""
    frame: list[str] = banner(width)
    frame.extend(clip(line, width) for line in header_lines)
    for title, lines in sections:
        frame.extend(section(title, lines, width))
    frame.append(separator(width))
    return "\n".join(frame)
