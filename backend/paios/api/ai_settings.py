"""Persisted AI settings: <data_dir>/ai-settings.json.

What the Settings UI and first-run setup write and what composition
reads. Precedence stays: environment variables > this file > ApiConfig
defaults (assistant_support.resolve_provider applies the env override).

API keys are never stored in plain text on Windows: they go through
DPAPI (CryptProtectData), bound to the current user account. On other
platforms the key is kept out of the file entirely — the provider SDKs
read their own environment variables there.
"""

import base64
import ctypes
import json
import os
from pathlib import Path

FILE_NAME = "ai-settings.json"
_DPAPI_PREFIX = "dpapi:"

#: provider -> the SDK's own key variable (the env alternative).
KEY_VARIABLES = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


def settings_path(data_dir: Path | str) -> Path:
    return Path(data_dir) / FILE_NAME


def load(data_dir: Path | str) -> dict:
    """The stored settings, or {} when absent/corrupt (never raises)."""
    try:
        payload = json.loads(
            settings_path(data_dir).read_text(encoding="utf-8")
        )
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError):
        return {}


def save(data_dir: Path | str, settings: dict) -> Path:
    target = settings_path(data_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    merged = load(data_dir)
    merged.update(settings)
    target.write_text(
        json.dumps(merged, indent=2, sort_keys=True), encoding="utf-8"
    )
    return target


# --- DPAPI (Windows user-bound encryption) ----------------------------------


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_ulong),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _blob(data: bytes) -> _DataBlob:
    buffer = ctypes.create_string_buffer(data, len(data))
    return _DataBlob(
        len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
    )


def _crypt(data: bytes, protect: bool) -> bytes | None:
    blob_in = _blob(data)
    blob_out = _DataBlob()
    function = (
        ctypes.windll.crypt32.CryptProtectData
        if protect
        else ctypes.windll.crypt32.CryptUnprotectData
    )
    if not function(
        ctypes.byref(blob_in), None, None, None, None, 0,
        ctypes.byref(blob_out),
    ):
        return None
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def protect_key(plain: str) -> str | None:
    """Plain key -> storable string, or None when the platform cannot
    protect it (callers must then NOT store it)."""
    if os.name != "nt":
        return None
    try:
        encrypted = _crypt(plain.encode("utf-8"), protect=True)
    except Exception:
        return None
    if encrypted is None:
        return None
    return _DPAPI_PREFIX + base64.b64encode(encrypted).decode("ascii")


def unprotect_key(stored: str) -> str | None:
    if not stored.startswith(_DPAPI_PREFIX) or os.name != "nt":
        return None
    try:
        decrypted = _crypt(
            base64.b64decode(stored[len(_DPAPI_PREFIX):]), protect=False
        )
    except Exception:
        return None
    return decrypted.decode("utf-8") if decrypted is not None else None


# --- the settings surface ----------------------------------------------------


def store_api_key(data_dir: Path | str, provider: str, plain: str) -> bool:
    """Store a provider key DPAPI-protected. False when protection is
    unavailable — the caller should tell the user to use the provider's
    environment variable instead. The plain key is never written."""
    protected = protect_key(plain)
    if protected is None:
        return False
    settings = load(data_dir)
    keys = dict(settings.get("api_keys") or {})
    keys[provider] = protected
    save(data_dir, {"api_keys": keys})
    return True


def api_key_for(data_dir: Path | str, provider: str) -> str | None:
    """The stored (decrypted) key for a provider, or None. Environment
    variables are NOT consulted here — the SDKs do that themselves."""
    stored = (load(data_dir).get("api_keys") or {}).get(provider)
    if not isinstance(stored, str):
        return None
    return unprotect_key(stored)


def has_stored_key(data_dir: Path | str, provider: str) -> bool:
    return isinstance(
        (load(data_dir).get("api_keys") or {}).get(provider), str
    )
