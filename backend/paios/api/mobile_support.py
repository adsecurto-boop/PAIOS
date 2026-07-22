"""Mobile companion security: device pairing and token authentication.

The desktop is never exposed openly. Trust is established once, on the
desktop's initiative:

    1. The desktop (loopback only) calls POST /mobile/pairing/start and
       shows the 6-digit code to the user.
    2. The phone submits the code via POST /mobile/pair within the
       5-minute window and receives a bearer token — shown exactly once.
    3. Every later /mobile/* call carries Authorization: Bearer <token>.

Only the SHA-256 of each token is stored (mobile-devices.json in the
data dir); a leaked settings file reveals no usable credentials. Codes
are single-use and expire; devices can be listed and revoked from the
desktop. TLS is a deployment concern layered on later — the pairing
model is transport-agnostic.
"""

import hashlib
import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path

FILE_NAME = "mobile-devices.json"
CODE_TTL_MINUTES = 5


class MobileAuthError(Exception):
    """Pairing or authentication failed; the message is user-safe."""


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class PairingService:
    """Write-through JSON, same discipline as the planning stores.
    Timestamps come from the caller (clock discipline, C6)."""

    def __init__(self, data_dir: Path | str) -> None:
        self._path = Path(data_dir) / FILE_NAME

    # --- storage ---------------------------------------------------------

    def _load(self) -> dict:
        if not self._path.is_file():
            return {"devices": {}, "pending": None}
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"devices": {}, "pending": None}
        if not isinstance(payload, dict):
            return {"devices": {}, "pending": None}
        payload.setdefault("devices", {})
        payload.setdefault("pending", None)
        return payload

    def _save(self, payload: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )

    # --- pairing ---------------------------------------------------------

    def begin(self, now: datetime) -> dict:
        """A fresh single-use code (any previous pending code dies)."""
        code = f"{secrets.randbelow(1_000_000):06d}"
        expires = now + timedelta(minutes=CODE_TTL_MINUTES)
        payload = self._load()
        payload["pending"] = {
            "code_sha256": _hash(code),
            "expires_at": expires.isoformat(),
        }
        self._save(payload)
        return {"code": code, "expires_at": expires.isoformat()}

    def complete(
        self, code: str, device_name: str, now: datetime
    ) -> tuple[str, str]:
        """(device_id, raw token). The raw token is returned exactly
        once and never stored."""
        payload = self._load()
        pending = payload.get("pending")
        if not pending:
            raise MobileAuthError(
                "No pairing in progress — start pairing on the desktop"
                " first."
            )
        if now > datetime.fromisoformat(pending["expires_at"]):
            payload["pending"] = None
            self._save(payload)
            raise MobileAuthError(
                "The pairing code expired — start pairing again."
            )
        if _hash(str(code).strip()) != pending["code_sha256"]:
            raise MobileAuthError("Wrong pairing code.")
        token = secrets.token_urlsafe(32)
        device_id = f"device_{secrets.token_hex(6)}"
        payload["devices"][device_id] = {
            "name": str(device_name).strip() or "Mobile device",
            "token_sha256": _hash(token),
            "paired_at": now.isoformat(),
            "last_seen": now.isoformat(),
        }
        payload["pending"] = None  # single use
        self._save(payload)
        return device_id, token

    # --- authentication --------------------------------------------------

    def authenticate(
        self, token: str | None, now: datetime | None = None
    ) -> str | None:
        """Bearer token -> device_id, or None. Constant-shape lookup
        over stored hashes; updates last_seen when a clock is given."""
        if not token:
            return None
        wanted = _hash(token)
        payload = self._load()
        for device_id, device in payload["devices"].items():
            if secrets.compare_digest(
                device.get("token_sha256", ""), wanted
            ):
                if now is not None:
                    device["last_seen"] = now.isoformat()
                    self._save(payload)
                return device_id
        return None

    # --- administration (desktop-side) ------------------------------------

    def devices(self) -> list[dict]:
        payload = self._load()
        return [
            {
                "device_id": device_id,
                "name": device["name"],
                "paired_at": device.get("paired_at"),
                "last_seen": device.get("last_seen"),
            }
            for device_id, device in sorted(payload["devices"].items())
        ]

    def revoke(self, device_id: str) -> bool:
        payload = self._load()
        if device_id not in payload["devices"]:
            return False
        del payload["devices"][device_id]
        self._save(payload)
        return True


def bearer_token(headers: dict | None) -> str | None:
    """The Authorization: Bearer value, case-insensitively."""
    if not headers:
        return None
    for name, value in headers.items():
        if str(name).lower() == "authorization":
            text = str(value).strip()
            if text.lower().startswith("bearer "):
                return text[7:].strip()
    return None


def is_loopback(client_host: str | None) -> bool:
    """Pairing administration is desktop-only. None means the call came
    through the router directly (tests, in-process callers) — local by
    definition."""
    return client_host is None or client_host in ("127.0.0.1", "::1")
