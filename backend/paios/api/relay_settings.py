"""Persisted remote-access (relay) settings: <data_dir>/relay-settings.json.

What the Networking page's Remote section writes and what the server
reads to run the outbound connector. The relay account key is a
credential, so it is protected exactly like the cloud AI keys — DPAPI on
Windows, kept out of the file entirely elsewhere (the connector then
needs the key supplied through the environment).

Reuses ``ai_settings``' DPAPI helpers rather than duplicating them.
"""

import json
from pathlib import Path

from paios.api import ai_settings

FILE_NAME = "relay-settings.json"
KEY_FIELD = "account_key"
#: The env fallback when secure storage is unavailable (non-Windows).
KEY_VARIABLE = "PAIOS_RELAY_ACCOUNT_KEY"


def settings_path(data_dir: Path | str) -> Path:
    return Path(data_dir) / FILE_NAME


def load(data_dir: Path | str) -> dict:
    try:
        payload = json.loads(settings_path(data_dir).read_text("utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError):
        return {}


def save(data_dir: Path | str, updates: dict) -> Path:
    target = settings_path(data_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    merged = load(data_dir)
    merged.update(updates)
    target.write_text(
        json.dumps(merged, indent=2, sort_keys=True), encoding="utf-8"
    )
    return target


def store_account_key(data_dir: Path | str, plain: str) -> bool:
    """Store the relay account key DPAPI-protected. False when the
    platform cannot protect it (the caller then tells the user to set
    PAIOS_RELAY_ACCOUNT_KEY instead); the plain key is never written."""
    protected = ai_settings.protect_key(plain)
    if protected is None:
        return False
    save(data_dir, {KEY_FIELD: protected})
    return True


def account_key_for(data_dir: Path | str) -> str | None:
    """The stored (decrypted) account key, or the env fallback, or None."""
    import os

    stored = load(data_dir).get(KEY_FIELD)
    if isinstance(stored, str):
        decrypted = ai_settings.unprotect_key(stored)
        if decrypted is not None:
            return decrypted
    return os.environ.get(KEY_VARIABLE) or None


def config(data_dir: Path | str) -> dict:
    """The safe, storable view (never the key itself)."""
    stored = load(data_dir)
    return {
        "enabled": bool(stored.get("enabled")),
        "relay_url": stored.get("relay_url") or "",
        "account": stored.get("account") or "default",
        "has_key": account_key_for(data_dir) is not None,
    }
