"""GUI settings persistence (M20): one small JSON file, nothing else.

The one sanctioned local-file surface besides the log sink: the first
run wizard's answers land in %APPDATA%/PAIOS/gui-settings.json (falling
back to ~/.paios/ where APPDATA is absent). Domain data still never
touches the GUI's disk — this file holds presentation preferences only.

Precedence at startup: defaults < settings file < CLI flags.
"""

import json
import os
from pathlib import Path

FILE_NAME = "gui-settings.json"


def settings_path() -> Path:
    """%APPDATA%/PAIOS/gui-settings.json, or ~/.paios/gui-settings.json."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "PAIOS" / FILE_NAME
    return Path.home() / ".paios" / FILE_NAME


def load_settings(path: Path | None = None) -> dict:
    """The stored settings, or {} when absent/corrupt (never raises)."""
    target = path if path is not None else settings_path()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(settings: dict, path: Path | None = None) -> Path:
    """Write (merging over what exists) and return the file path."""
    target = path if path is not None else settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    merged = load_settings(target)
    merged.update(settings)
    target.write_text(
        json.dumps(merged, indent=2, sort_keys=True), encoding="utf-8"
    )
    return target


def first_run_complete(settings: dict) -> bool:
    return bool(settings.get("first_run_complete"))
