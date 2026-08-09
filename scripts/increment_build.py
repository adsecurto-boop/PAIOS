"""Increment PAIOS build number inside backend/paios/__init__.py."""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INIT_FILE = REPO_ROOT / "backend" / "paios" / "__init__.py"


def main() -> int:
    if not INIT_FILE.is_file():
        print(f"Error: {INIT_FILE} not found.")
        return 1

    content = INIT_FILE.read_text(encoding="utf-8")
    match = re.search(r'^__build__\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if not match:
        print("Error: __build__ not found in __init__.py")
        return 1

    current_build_str = match.group(1)
    try:
        current_build = int(current_build_str)
    except ValueError:
        print(f"Error: __build__ value {current_build_str!r} is not numeric.")
        return 1

    next_build = current_build + 1
    next_build_str = f"{next_build:03d}"

    updated_content = re.sub(
        r'^__build__\s*=\s*"([^"]+)"',
        f'__build__ = "{next_build_str}"',
        content,
        flags=re.MULTILINE,
    )
    INIT_FILE.write_text(updated_content, encoding="utf-8")
    print(f"PAIOS build incremented: {current_build_str} -> {next_build_str}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
