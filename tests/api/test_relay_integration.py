"""Remote-access desktop integration (M23): settings persistence, the
/system/relay REST surface, the pairing -> relay-authorize bridge, and
the ApiServer connector lifecycle. No real relay is contacted."""

import ctypes

import pytest

from paios.api import relay_settings
from paios.api.mobile_support import PairingService
from paios.api.routes import ApiRouter


def ok(router, method, path, body=None, expect=200, **ctx):
    status, payload = router.handle(method, path, body, **ctx)
    assert status == expect, payload
    return payload


class TestRelaySettings:
    def test_config_defaults(self, tmp_path):
        config = relay_settings.config(tmp_path)
        assert config == {
            "enabled": False, "relay_url": "", "account": "default",
            "has_key": False,
        }

    def test_save_and_config_roundtrip(self, tmp_path):
        relay_settings.save(
            tmp_path,
            {"enabled": True, "relay_url": "https://r.example.com",
             "account": "me"},
        )
        config = relay_settings.config(tmp_path)
        assert config["enabled"] is True
        assert config["relay_url"] == "https://r.example.com"
        assert config["account"] == "me"

    def test_account_key_from_env_when_no_secure_store(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("PAIOS_RELAY_ACCOUNT_KEY", "env-key")
        assert relay_settings.account_key_for(tmp_path) == "env-key"
        assert relay_settings.config(tmp_path)["has_key"] is True

    @pytest.mark.skipif(
        not hasattr(ctypes, "windll"), reason="DPAPI is Windows-only"
    )
    def test_key_is_stored_protected(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PAIOS_RELAY_ACCOUNT_KEY", raising=False)
        assert relay_settings.store_account_key(tmp_path, "secret-key")
        raw = relay_settings.settings_path(tmp_path).read_text("utf-8")
        assert "secret-key" not in raw  # never plain on disk
        assert relay_settings.account_key_for(tmp_path) == "secret-key"


def relay_router(api_app, tmp_path, *, authorize=None, reloads=None):
    state = {"connected": False}
    data_dir = tmp_path / "relay-data"
    data_dir.mkdir(parents=True, exist_ok=True)

    def status():
        # Mirrors the real server: config first, then live connection.
        return {
            **relay_settings.config(data_dir),
            "connected": state["connected"],
            "last_error": None,
        }

    def reload():
        if reloads is not None:
            reloads.append(True)
        state["connected"] = relay_settings.config(data_dir)["enabled"]

    return ApiRouter(
        api_app,
        network_dir=data_dir,
        bound_host="127.0.0.1",
        bound_port=8765,
        mobile=PairingService(data_dir),
        relay_status=status,
        relay_reload=reload,
        relay_authorize=authorize if authorize is not None else (lambda h: False),
    )


class TestRelayRest:
    def test_get_relay_status(self, api_app, tmp_path):
        router = relay_router(api_app, tmp_path)
        payload = ok(router, "GET", "/system/relay")
        assert payload["enabled"] is False
        assert payload["connected"] is False

    def test_uncomposed_relay_is_503(self, api_app):
        status, _ = ApiRouter(api_app).handle("GET", "/system/relay")
        assert status == 503

    def test_put_enables_and_reconnects(self, api_app, tmp_path):
        reloads = []
        router = relay_router(api_app, tmp_path, reloads=reloads)
        payload = ok(
            router, "PUT", "/system/relay",
            {"enabled": True, "relay_url": "https://r.example.com",
             "account": "me"},
        )
        assert reloads == [True]  # settings applied live
        assert payload["enabled"] is True
        assert payload["relay_url"] == "https://r.example.com"

    def test_put_is_loopback_only(self, api_app, tmp_path):
        router = relay_router(api_app, tmp_path)
        status, _ = router.handle(
            "PUT", "/system/relay", {"enabled": True},
            client_host="192.168.1.50",
        )
        assert status == 403


class TestPairingBridge:
    def test_pairing_authorizes_with_relay_when_on(self, api_app, tmp_path):
        seen = []
        router = relay_router(
            api_app, tmp_path, authorize=lambda h: seen.append(h) or True
        )
        started = ok(router, "POST", "/mobile/pairing/start")
        paired = ok(
            router, "POST", "/mobile/pair",
            {"code": started["code"], "device_name": "Pixel"}, expect=201,
        )
        assert paired["remote_enabled"] is True
        # The relay was told the SHA-256 of the issued token.
        import hashlib

        assert seen == [
            hashlib.sha256(paired["token"].encode()).hexdigest()
        ]

    def test_pairing_without_relay_reports_not_remote(
        self, api_app, tmp_path
    ):
        router = relay_router(api_app, tmp_path)  # authorize returns False
        started = ok(router, "POST", "/mobile/pairing/start")
        paired = ok(
            router, "POST", "/mobile/pair", {"code": started["code"]},
            expect=201,
        )
        assert paired["remote_enabled"] is False


class TestServerRelayLifecycle:
    def test_server_starts_and_stops_connector_when_enabled(
        self, tmp_path, monkeypatch
    ):
        from paios.api import ApiConfig, ApiServer
        from paios.system import relay_client

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        relay_settings.save(
            data_dir,
            {"enabled": True, "relay_url": "https://r.example.com",
             "account": "me"},
        )
        monkeypatch.setenv("PAIOS_RELAY_ACCOUNT_KEY", "env-key")

        started, stopped = [], []

        class FakeConnector:
            def __init__(self, url, account, key, local, **kwargs):
                self.url = url

            def start(self):
                started.append(self.url)

            def stop(self):
                stopped.append(self.url)

            def status(self):
                return {"connected": True, "last_error": None}

            def authorize_device(self, token_hash):
                return True

        monkeypatch.setattr(relay_client, "RelayConnector", FakeConnector)
        server = ApiServer(
            ApiConfig(host="127.0.0.1", port=0, data_dir=str(data_dir))
        )
        server.start()
        try:
            assert started == ["https://r.example.com"]
            assert server._relay_status()["connected"] is True
        finally:
            server.shutdown()
        assert stopped == ["https://r.example.com"]

    def test_server_leaves_relay_off_when_disabled(self, tmp_path):
        from paios.api import ApiConfig, ApiServer

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        server = ApiServer(
            ApiConfig(host="127.0.0.1", port=0, data_dir=str(data_dir))
        )
        server.start()
        try:
            assert server._relay_connector is None
            assert server._relay_status()["connected"] is False
        finally:
            server.shutdown()
