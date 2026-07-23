"""The portable PAIOS relay server.

A tiny, dependency-free reverse-tunnel broker. The desktop dials out and
long-polls; a phone anywhere reaches its desktop through this one public
endpoint. Neither PAIOS process accepts inbound connections — only the
relay does, so the laptop is never exposed.

Run it anywhere with one command:

    python relay.py                     # or: python -m paios_relay
    docker compose up -d

Configuration is entirely environment variables (12-factor; no code
change to deploy on Oracle Cloud, a Raspberry Pi, DigitalOcean, Hetzner,
AWS or Azure):

    PAIOS_RELAY_SECRET        HS256 signing secret for phone tokens (req.)
    PAIOS_RELAY_ACCOUNT       the desktop account id           (default "default")
    PAIOS_RELAY_ACCOUNT_KEY   the desktop's shared credential  (req.)
    PAIOS_RELAY_HOST          bind host                        (default 0.0.0.0)
    PAIOS_RELAY_PORT          bind port                        (default 8770)
    PAIOS_RELAY_TLS_CERT      PEM cert path -> serve HTTPS      (optional)
    PAIOS_RELAY_TLS_KEY       PEM key path                     (optional)
    PAIOS_RELAY_POLL_SECONDS  desktop long-poll window         (default 25)

TLS: point TLS_CERT/TLS_KEY at a certificate to serve HTTPS directly, or
omit them and terminate TLS at a reverse proxy (Caddy/nginx/Traefik) —
both are documented in the README.
"""

import hashlib
import hmac
import json
import os
import ssl
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from paios_relay.auth import ReplayGuard, TokenIssuer
from paios_relay.hub import RelayHub

_MAX_BODY_BYTES = 2_000_000


@dataclass(frozen=True)
class RelayConfig:
    secret: str
    account_key: str
    account: str = "default"
    host: str = "0.0.0.0"
    port: int = 8770
    tls_cert: str | None = None
    tls_key: str | None = None
    poll_seconds: float = 25.0
    request_timeout: float = 30.0

    @classmethod
    def from_env(cls, environ=None) -> "RelayConfig":
        env = environ if environ is not None else os.environ
        secret = env.get("PAIOS_RELAY_SECRET", "")
        account_key = env.get("PAIOS_RELAY_ACCOUNT_KEY", "")
        if not secret or not account_key:
            raise ValueError(
                "PAIOS_RELAY_SECRET and PAIOS_RELAY_ACCOUNT_KEY are"
                " required — set them before starting the relay."
            )
        return cls(
            secret=secret,
            account_key=account_key,
            account=env.get("PAIOS_RELAY_ACCOUNT", "default"),
            host=env.get("PAIOS_RELAY_HOST", "0.0.0.0"),
            port=int(env.get("PAIOS_RELAY_PORT", "8770")),
            tls_cert=env.get("PAIOS_RELAY_TLS_CERT") or None,
            tls_key=env.get("PAIOS_RELAY_TLS_KEY") or None,
            poll_seconds=float(env.get("PAIOS_RELAY_POLL_SECONDS", "25")),
        )


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class RelayApp:
    """The pure request core: (method, path, body, headers) -> (status,
    payload). No sockets — the HTTP handler binds it to the wire; tests
    call ``handle`` directly."""

    def __init__(self, config: RelayConfig, now=time.time) -> None:
        self._config = config
        self._hub = RelayHub()
        self._issuer = TokenIssuer(config.secret)
        self._replay = ReplayGuard()
        self._now = now

    @property
    def hub(self) -> RelayHub:
        return self._hub

    # --- helpers ---------------------------------------------------------

    def _desktop_ok(self, headers: dict) -> str | None:
        """The authenticated account id, or None. The desktop proves
        itself with its account key (constant-time compare)."""
        account = (headers or {}).get("X-Relay-Account", self._config.account)
        key = (headers or {}).get("X-Relay-Key", "")
        if account == self._config.account and hmac.compare_digest(
            key, self._config.account_key
        ):
            return account
        return None

    def _bearer(self, headers: dict) -> str | None:
        value = (headers or {}).get("Authorization", "")
        if value.lower().startswith("bearer "):
            return value[7:].strip()
        return None

    # --- dispatch --------------------------------------------------------

    def handle(self, method, path, body, headers=None):
        try:
            return self._dispatch(method.upper(), path, body or {}, headers)
        except _RelayError as error:
            return error.status, {"error": error.message}
        except Exception as error:  # never leak a stack to the wire
            return 500, {"error": f"relay error: {error}"}

    def _dispatch(self, method, path, body, headers):
        route = (method, path)
        if route == ("GET", "/health"):
            return 200, {"ok": True, "service": "paios-relay"}
        if route == ("GET", "/desktop/poll"):
            return self._desktop_poll(headers)
        if route == ("POST", "/desktop/respond"):
            return self._desktop_respond(body, headers)
        if route == ("POST", "/desktop/authorize"):
            return self._desktop_authorize(body, headers)
        if route == ("POST", "/desktop/revoke"):
            return self._desktop_revoke(body, headers)
        if route == ("POST", "/phone/token"):
            return self._phone_token(body)
        if route == ("POST", "/phone/refresh"):
            return self._phone_refresh(body)
        if route == ("POST", "/phone/request"):
            return self._phone_request(body, headers)
        return 404, {"error": f"unknown route {method} {path}"}

    # --- desktop side ----------------------------------------------------

    def _desktop_poll(self, headers):
        account = self._require_desktop(headers)
        requests = self._hub.poll_requests(
            account, self._now(), self._config.poll_seconds
        )
        return 200, {"requests": requests}

    def _desktop_respond(self, body, headers):
        self._require_desktop(headers)
        request_id = body.get("id")
        if not request_id:
            raise _RelayError(400, "missing request id")
        self._hub.submit_response(
            request_id,
            {
                "status": int(body.get("status", 200)),
                "body": body.get("body"),
            },
        )
        return 200, {"delivered": True}

    def _desktop_authorize(self, body, headers):
        account = self._require_desktop(headers)
        token_hash = body.get("token_hash")
        if not token_hash:
            raise _RelayError(400, "missing token_hash")
        self._hub.authorize_device(account, token_hash)
        return 200, {"authorized": True}

    def _desktop_revoke(self, body, headers):
        account = self._require_desktop(headers)
        self._hub.revoke_device(account, body.get("token_hash", ""))
        return 200, {"revoked": True}

    # --- phone side ------------------------------------------------------

    def _phone_token(self, body):
        account = body.get("account", self._config.account)
        device_token = body.get("device_token", "")
        device = body.get("device", "phone")
        if not device_token:
            raise _RelayError(400, "missing device_token")
        if not self._hub.is_authorized(account, sha256_hex(device_token)):
            raise _RelayError(
                401,
                "this device is not paired for remote access — pair it"
                " from PAIOS on the desktop while on the same Wi-Fi",
            )
        return 200, self._issuer.issue_pair(account, device, self._now())

    def _phone_refresh(self, body):
        refreshed = self._issuer.refresh(
            body.get("refresh_token", ""), self._now()
        )
        if refreshed is None:
            raise _RelayError(401, "invalid or expired refresh token")
        return 200, refreshed

    def _phone_request(self, body, headers):
        token = self._bearer(headers)
        claims = (
            self._issuer.verify_access(token, self._now()) if token else None
        )
        if claims is None:
            raise _RelayError(401, "invalid or expired access token")
        # Replay protection: each request carries a unique nonce + time.
        nonce = str(body.get("nonce", ""))
        timestamp = int(body.get("ts", 0))
        if not nonce or not self._replay.check(
            nonce, timestamp, int(self._now())
        ):
            raise _RelayError(409, "stale or replayed request")
        account = claims["account"]
        if not self._hub.is_desktop_online(account, self._now()):
            raise _RelayError(
                503, "your desktop is offline — PAIOS is not reachable"
                " right now",
            )
        request_id = self._hub.submit_request(
            account,
            {
                "method": body.get("method", "GET"),
                "path": body.get("path", "/"),
                "body": body.get("body"),
                # The phone's own PAIOS device token rides through opaquely
                # so the desktop's local API still authenticates it — the
                # relay authorises transport, PAIOS authorises the data.
                "headers": body.get("headers") or {},
                "device": claims.get("sub"),
            },
        )
        response = self._hub.await_response(
            request_id, self._config.request_timeout
        )
        if response is None:
            raise _RelayError(504, "the desktop did not respond in time")
        return 200, response

    # --- guards ----------------------------------------------------------

    def _require_desktop(self, headers) -> str:
        account = self._desktop_ok(headers)
        if account is None:
            raise _RelayError(401, "desktop authentication failed")
        return account


class _RelayError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class _Handler(BaseHTTPRequestHandler):
    server_version = "PaiosRelay/1.0"

    def _app(self) -> RelayApp:
        return self.server.app  # type: ignore[attr-defined]

    def _headers(self) -> dict:
        return {key: value for key, value in self.headers.items()}

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length == 0:
            return {}
        if length > _MAX_BODY_BYTES:
            return None
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None

    def _respond(self, status, payload):
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):  # noqa: N802
        status, payload = self._app().handle("GET", self.path, {}, self._headers())
        self._respond(status, payload)

    def do_POST(self):  # noqa: N802
        body = self._read_body()
        if body is None:
            self._respond(400, {"error": "invalid JSON body"})
            return
        status, payload = self._app().handle(
            "POST", self.path, body, self._headers()
        )
        self._respond(status, payload)

    def log_message(self, *args):  # keep the console quiet
        pass


def build_server(config: RelayConfig) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((config.host, config.port), _Handler)
    server.app = RelayApp(config)  # type: ignore[attr-defined]
    if config.tls_cert and config.tls_key:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(config.tls_cert, config.tls_key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
    return server


def main(argv=None) -> int:
    try:
        config = RelayConfig.from_env()
    except ValueError as error:
        print(f"Configuration error: {error}")
        return 2
    server = build_server(config)
    scheme = "https" if config.tls_cert else "http"
    print(
        f"PAIOS relay listening on {scheme}://{config.host}:{config.port}"
        f"  (account {config.account!r})"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
    return 0
