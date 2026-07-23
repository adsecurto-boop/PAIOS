"""Relay authentication: HS256 JWTs, refresh, and replay protection.

Stdlib only (hmac / hashlib / base64) — the relay, like the updater, is a
self-contained deployable that imports nothing from PAIOS. Clocks are
injected (``now`` epoch seconds) so every function is deterministic and
testable, matching the PAIOS clock discipline.

Token model:

    * a short-lived ACCESS token authorises phone -> relay requests;
    * a long-lived REFRESH token mints new access tokens without
      re-pairing;
    * both are bound to an ``account`` (one desktop) and a ``sub``
      (the paired device), so a token only ever reaches its own desktop.
"""

import base64
import hashlib
import hmac
import json

ACCESS_TTL_SECONDS = 15 * 60          # 15 minutes
REFRESH_TTL_SECONDS = 30 * 24 * 3600  # 30 days
DEFAULT_REPLAY_WINDOW_SECONDS = 300


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def _sign(segment: str, secret: str) -> str:
    digest = hmac.new(
        secret.encode("utf-8"), segment.encode("ascii"), hashlib.sha256
    ).digest()
    return _b64url(digest)


def encode(payload: dict, secret: str, now: int, ttl: int) -> str:
    """A compact HS256 JWT for ``payload`` valid for ``ttl`` seconds."""
    header = _b64url(b'{"alg":"HS256","typ":"JWT"}')
    body = dict(payload)
    body["iat"] = int(now)
    body["exp"] = int(now) + int(ttl)
    body_segment = _b64url(
        json.dumps(body, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )
    )
    signing_input = f"{header}.{body_segment}"
    return f"{signing_input}.{_sign(signing_input, secret)}"


def decode(token: str, secret: str, now: int) -> dict | None:
    """The verified claims, or None when the signature is wrong, the
    token is malformed, or it has expired. Constant-time signature check."""
    try:
        header_segment, body_segment, signature = token.split(".")
    except (ValueError, AttributeError):
        return None
    expected = _sign(f"{header_segment}.{body_segment}", secret)
    if not hmac.compare_digest(expected, signature):
        return None
    try:
        claims = json.loads(_b64url_decode(body_segment))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(claims, dict):
        return None
    if int(claims.get("exp", 0)) < int(now):
        return None
    return claims


class TokenIssuer:
    """Issues and validates the two token kinds for one relay secret."""

    def __init__(
        self,
        secret: str,
        access_ttl: int = ACCESS_TTL_SECONDS,
        refresh_ttl: int = REFRESH_TTL_SECONDS,
    ) -> None:
        if not secret:
            raise ValueError("relay secret must not be empty")
        self._secret = secret
        self._access_ttl = access_ttl
        self._refresh_ttl = refresh_ttl

    def issue_pair(self, account: str, device: str, now: int) -> dict:
        """A fresh access + refresh pair for a paired device."""
        base = {"account": account, "sub": device}
        return {
            "access_token": encode(
                {**base, "typ": "access"}, self._secret, now, self._access_ttl
            ),
            "refresh_token": encode(
                {**base, "typ": "refresh"},
                self._secret, now, self._refresh_ttl,
            ),
            "expires_in": self._access_ttl,
            "token_type": "Bearer",
        }

    def verify_access(self, token: str, now: int) -> dict | None:
        claims = decode(token, self._secret, now)
        if claims is None or claims.get("typ") != "access":
            return None
        return claims

    def refresh(self, refresh_token: str, now: int) -> dict | None:
        """A new pair from a valid refresh token (rotation), or None."""
        claims = decode(refresh_token, self._secret, now)
        if claims is None or claims.get("typ") != "refresh":
            return None
        return self.issue_pair(claims["account"], claims["sub"], now)


class ReplayGuard:
    """Rejects a nonce seen twice inside the window, and any request
    whose timestamp is outside it. Bounds memory by dropping expired
    nonces on each check — no background sweeper needed."""

    def __init__(self, window_seconds: int = DEFAULT_REPLAY_WINDOW_SECONDS):
        self._window = window_seconds
        self._seen: dict[str, int] = {}

    def check(self, nonce: str, timestamp: int, now: int) -> bool:
        """True when the request is fresh and unseen (and is recorded);
        False for a stale timestamp or a replayed nonce."""
        now = int(now)
        if abs(now - int(timestamp)) > self._window:
            return False
        # Expire old nonces.
        cutoff = now - self._window
        for seen_nonce in [n for n, t in self._seen.items() if t < cutoff]:
            del self._seen[seen_nonce]
        if nonce in self._seen:
            return False
        self._seen[nonce] = now
        return True
