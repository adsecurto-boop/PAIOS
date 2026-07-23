"""The relay request core (RelayApp) end to end, no sockets.

A controllable clock and small timeouts keep the one threaded full-flow
test deterministic and fast.
"""

import threading

import pytest

from paios_relay.server import RelayApp, RelayConfig, sha256_hex


def make_app(now_ref):
    config = RelayConfig(
        secret="test-secret",
        account_key="desk-key",
        account="default",
        poll_seconds=0.3,
        request_timeout=3.0,
    )
    return RelayApp(config, now=lambda: now_ref[0])


DESKTOP = {"X-Relay-Account": "default", "X-Relay-Key": "desk-key"}


class TestConfig:
    def test_from_env_requires_secrets(self):
        with pytest.raises(ValueError):
            RelayConfig.from_env({})

    def test_from_env_reads_values(self):
        config = RelayConfig.from_env(
            {
                "PAIOS_RELAY_SECRET": "s",
                "PAIOS_RELAY_ACCOUNT_KEY": "k",
                "PAIOS_RELAY_PORT": "9000",
            }
        )
        assert config.secret == "s" and config.port == 9000


class TestHealthAndAuth:
    def test_health(self):
        status, payload = make_app([1000]).handle("GET", "/health", {})
        assert status == 200 and payload["ok"] is True

    def test_desktop_poll_requires_key(self):
        app = make_app([1000])
        status, _ = app.handle("GET", "/desktop/poll", {}, {})
        assert status == 401
        status, _ = app.handle(
            "GET", "/desktop/poll", {},
            {"X-Relay-Account": "default", "X-Relay-Key": "wrong"},
        )
        assert status == 401

    def test_unpaired_phone_cannot_get_a_token(self):
        app = make_app([1000])
        status, _ = app.handle(
            "POST", "/phone/token",
            {"device_token": "never-paired", "device": "x"},
        )
        assert status == 401


class TestTokensAndRefresh:
    def test_authorized_phone_gets_and_refreshes_tokens(self):
        now = [1000]
        app = make_app(now)
        token = "device-token-abc"
        app.handle(
            "POST", "/desktop/authorize",
            {"token_hash": sha256_hex(token)}, DESKTOP,
        )
        status, pair = app.handle(
            "POST", "/phone/token",
            {"device_token": token, "device": "pixel"},
        )
        assert status == 200 and pair["access_token"]
        status, refreshed = app.handle(
            "POST", "/phone/refresh",
            {"refresh_token": pair["refresh_token"]},
        )
        assert status == 200 and refreshed["access_token"]

    def test_refresh_rejects_bogus_token(self):
        status, _ = make_app([1000]).handle(
            "POST", "/phone/refresh", {"refresh_token": "nope"}
        )
        assert status == 401


class TestForwarding:
    def _authorized_access(self, app, now):
        token = "device-token-abc"
        app.handle(
            "POST", "/desktop/authorize",
            {"token_hash": sha256_hex(token)}, DESKTOP,
        )
        _, pair = app.handle(
            "POST", "/phone/token",
            {"device_token": token, "device": "pixel"},
        )
        return pair["access_token"]

    def test_full_phone_to_desktop_roundtrip(self):
        now = [1000]
        app = make_app(now)
        access = self._authorized_access(app, now)
        app.hub.desktop_connected("default", now[0])  # desktop is online

        captured = {}

        def phone():
            captured["result"] = app.handle(
                "POST", "/phone/request",
                {
                    "method": "GET", "path": "/status",
                    "nonce": "n1", "ts": now[0],
                },
                {"Authorization": f"Bearer {access}"},
            )

        caller = threading.Thread(target=phone)
        caller.start()
        # The desktop long-polls until the request arrives, then answers.
        drained = []
        deadline = 0
        while not drained and deadline < 20:
            _, payload = app.handle("GET", "/desktop/poll", {}, DESKTOP)
            drained = payload["requests"]
            deadline += 1
        assert drained, "desktop never received the forwarded request"
        app.handle(
            "POST", "/desktop/respond",
            {"id": drained[0]["id"], "status": 200,
             "body": {"operational": True}},
            DESKTOP,
        )
        caller.join(timeout=5)
        status, response = captured["result"]
        assert status == 200
        assert response["status"] == 200
        assert response["body"] == {"operational": True}

    def test_request_without_token_is_401(self):
        app = make_app([1000])
        status, _ = app.handle(
            "POST", "/phone/request",
            {"path": "/status", "nonce": "n", "ts": 1000}, {},
        )
        assert status == 401

    def test_replayed_nonce_is_rejected(self):
        now = [1000]
        app = make_app(now)
        access = self._authorized_access(app, now)
        app.hub.desktop_connected("default", now[0])
        bearer = {"Authorization": f"Bearer {access}"}
        body = {"path": "/status", "nonce": "same", "ts": now[0]}
        # First one blocks (no desktop responder), but the nonce is
        # consumed before the wait; run it briefly in a thread.
        threading.Thread(
            target=lambda: app.handle("POST", "/phone/request", body, bearer),
            daemon=True,
        ).start()
        import time
        time.sleep(0.1)
        status, _ = app.handle("POST", "/phone/request", body, bearer)
        assert status == 409

    def test_offline_desktop_returns_503(self):
        now = [1000]
        app = make_app(now)
        access = self._authorized_access(app, now)
        # No desktop_connected -> offline.
        status, _ = app.handle(
            "POST", "/phone/request",
            {"path": "/status", "nonce": "n1", "ts": now[0]},
            {"Authorization": f"Bearer {access}"},
        )
        assert status == 503
