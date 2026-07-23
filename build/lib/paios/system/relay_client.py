"""Desktop side of remote access (M23): dial out to the relay and serve
the phone's requests against the local PAIOS API.

The desktop never accepts an inbound connection. It opens an *outbound*
long-poll to the relay; each phone request the relay hands back is
executed against ``http://127.0.0.1:<port>`` (the same REST API the LAN
uses) and the response is posted back. The long-poll is also the
heartbeat, and a dropped connection reconnects with capped backoff — so
the phone sees "desktop offline" only while it truly is.

Stdlib only. The HTTP seam is injectable, so the whole connector is
unit-tested with no relay and no server.
"""

import json
import logging
import threading
import time
import urllib.error
import urllib.request

logger = logging.getLogger("paios.relay")

_BACKOFF_SECONDS = (1, 2, 5, 10, 20, 30)


def default_http(method, url, body=None, headers=None, timeout=30.0):
    """One HTTP exchange -> (status, decoded-json-or-None). Network
    errors raise; HTTP error statuses return their (code, payload)."""
    data = None
    all_headers = {"Accept": "application/json"}
    if headers:
        all_headers.update(headers)
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        all_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url, data=data, headers=all_headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as reply:
            raw = reply.read().decode("utf-8")
            return reply.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as error:
        try:
            payload = json.loads(error.read().decode("utf-8"))
        except Exception:
            payload = None
        return error.code, payload


class RelayConnector:
    """Runs the desktop's outbound tunnel to one relay account."""

    def __init__(
        self,
        relay_url: str,
        account: str,
        account_key: str,
        local_api_url: str,
        *,
        http=default_http,
        sleep=time.sleep,
        poll_timeout: float = 30.0,
    ) -> None:
        self._relay = relay_url.rstrip("/")
        self._account = account
        self._account_key = account_key
        self._local = local_api_url.rstrip("/")
        self._http = http
        self._sleep = sleep
        self._poll_timeout = poll_timeout
        self._running = threading.Event()
        self._thread: threading.Thread | None = None
        self._connected = False
        self._last_error: str | None = None

    # --- headers ---------------------------------------------------------

    def _desktop_headers(self) -> dict:
        return {
            "X-Relay-Account": self._account,
            "X-Relay-Key": self._account_key,
        }

    # --- pairing bridge --------------------------------------------------

    def authorize_device(self, token_hash: str) -> bool:
        """Tell the relay a freshly paired phone may reach this desktop.
        Called after local pairing; safe to call when the relay is down
        (returns False, retried on the next pairing/refresh)."""
        try:
            status, _ = self._http(
                "POST",
                f"{self._relay}/desktop/authorize",
                {"token_hash": token_hash},
                self._desktop_headers(),
                timeout=10.0,
            )
        except OSError as error:
            self._last_error = str(error)
            return False
        return status == 200

    # --- lifecycle -------------------------------------------------------

    @property
    def connected(self) -> bool:
        return self._connected

    def status(self) -> dict:
        return {
            "relay_url": self._relay,
            "account": self._account,
            "connected": self._connected,
            "last_error": self._last_error,
        }

    def start(self) -> None:
        if self._running.is_set():
            return
        self._running.set()
        self._thread = threading.Thread(
            target=self._loop, name="paios-relay-connector", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._running.clear()
        if self._thread is not None:
            self._thread.join(timeout=self._poll_timeout + 2)
            self._thread = None
        self._connected = False

    # --- the outbound loop ----------------------------------------------

    def _loop(self) -> None:
        attempt = 0
        while self._running.is_set():
            try:
                self._poll_once()
                self._connected = True
                self._last_error = None
                attempt = 0
            except Exception as error:  # relay down / network blip
                self._connected = False
                self._last_error = str(error)
                logger.info("relay poll failed: %s", error)
                delay = _BACKOFF_SECONDS[min(attempt, len(_BACKOFF_SECONDS) - 1)]
                attempt += 1
                self._sleep(delay)

    def poll_once(self) -> int:
        """One poll+forward cycle (for tests and single-step runs);
        returns how many requests were served."""
        return self._poll_once()

    def _poll_once(self) -> int:
        status, payload = self._http(
            "GET",
            f"{self._relay}/desktop/poll",
            None,
            self._desktop_headers(),
            timeout=self._poll_timeout,
        )
        if status != 200 or not isinstance(payload, dict):
            raise OSError(f"relay poll returned {status}")
        requests = payload.get("requests") or []
        for request in requests:
            self._serve(request)
        return len(requests)

    def _serve(self, request: dict) -> None:
        """Execute one forwarded request against the local API and post
        the result back. A local failure still returns a response so the
        phone is never left hanging."""
        request_id = request.get("id")
        try:
            status, body = self._http(
                request.get("method", "GET"),
                self._local + request.get("path", "/"),
                request.get("body"),
                request.get("headers") or {},
                timeout=self._poll_timeout,
            )
        except Exception as error:
            status, body = 502, {"error": f"local API error: {error}"}
        try:
            self._http(
                "POST",
                f"{self._relay}/desktop/respond",
                {"id": request_id, "status": status, "body": body},
                self._desktop_headers(),
                timeout=10.0,
            )
        except Exception as error:
            logger.info("relay respond failed: %s", error)
