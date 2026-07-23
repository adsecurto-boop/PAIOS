"""The reverse-tunnel core: route phone requests to the right desktop
and carry responses back, without either side accepting inbound
connections.

The desktop dials out and long-polls ``poll_requests``; a phone's
request is enqueued for its account and the phone waits on
``await_response`` until the desktop posts one. Everything is in-memory
and thread-safe — the relay is stateless across restarts by design
(tokens are self-contained JWTs; a dropped desktop simply reconnects).

Stdlib only, no PAIOS imports. Clocks are injected for heartbeat checks.
"""

import threading
import uuid
from collections import deque
from dataclasses import dataclass, field


@dataclass
class _Account:
    #: SHA-256 hashes of the device tokens allowed to reach this desktop.
    authorized: set = field(default_factory=set)
    pending: deque = field(default_factory=deque)
    last_seen: float = 0.0
    connected: bool = False
    condition: threading.Condition = field(
        default_factory=lambda: threading.Condition()
    )


@dataclass
class _Pending:
    event: threading.Event
    response: dict | None = None


class RelayHub:
    """One relay instance's live routing state."""

    def __init__(self, offline_seconds: float = 30.0) -> None:
        self._accounts: dict[str, _Account] = {}
        self._pending: dict[str, _Pending] = {}
        self._lock = threading.Lock()
        self._offline_seconds = offline_seconds

    def _account(self, account_id: str) -> _Account:
        with self._lock:
            account = self._accounts.get(account_id)
            if account is None:
                account = _Account()
                self._accounts[account_id] = account
            return account

    # --- authorization (desktop tells the relay which phones are ok) -----

    def authorize_device(self, account_id: str, token_hash: str) -> None:
        self._account(account_id).authorized.add(token_hash)

    def revoke_device(self, account_id: str, token_hash: str) -> None:
        self._account(account_id).authorized.discard(token_hash)

    def is_authorized(self, account_id: str, token_hash: str) -> bool:
        return token_hash in self._account(account_id).authorized

    # --- desktop presence + heartbeat ------------------------------------

    def desktop_connected(self, account_id: str, now: float) -> None:
        account = self._account(account_id)
        with account.condition:
            account.connected = True
            account.last_seen = now

    def desktop_disconnected(self, account_id: str) -> None:
        account = self._account(account_id)
        with account.condition:
            account.connected = False
            account.condition.notify_all()

    def touch(self, account_id: str, now: float) -> None:
        self._account(account_id).last_seen = now

    def is_desktop_online(self, account_id: str, now: float) -> bool:
        account = self._account(account_id)
        return (
            account.connected
            and (now - account.last_seen) <= self._offline_seconds
        )

    # --- phone -> desktop -------------------------------------------------

    def submit_request(self, account_id: str, request: dict) -> str:
        """Queue a phone request for the desktop; returns its id. Wakes a
        long-polling desktop immediately."""
        request_id = uuid.uuid4().hex
        entry = {"id": request_id, **request}
        self._pending[request_id] = _Pending(event=threading.Event())
        account = self._account(account_id)
        with account.condition:
            account.pending.append(entry)
            account.condition.notify_all()
        return request_id

    def await_response(
        self, request_id: str, timeout: float
    ) -> dict | None:
        pending = self._pending.get(request_id)
        if pending is None:
            return None
        got = pending.event.wait(timeout)
        response = pending.response if got else None
        self._pending.pop(request_id, None)
        return response

    # --- desktop side -----------------------------------------------------

    def poll_requests(
        self, account_id: str, now: float, timeout: float
    ) -> list[dict]:
        """Long-poll: block until at least one request is queued or the
        timeout elapses. Doubles as the heartbeat (updates last_seen)."""
        account = self._account(account_id)
        with account.condition:
            account.connected = True
            account.last_seen = now
            if not account.pending:
                account.condition.wait(timeout)
            drained = list(account.pending)
            account.pending.clear()
            return drained

    def submit_response(self, request_id: str, response: dict) -> bool:
        pending = self._pending.get(request_id)
        if pending is None:
            return False
        pending.response = response
        pending.event.set()
        return True
