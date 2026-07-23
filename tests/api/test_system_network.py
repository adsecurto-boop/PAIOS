"""The /system networking endpoints (M21): facts, the access-mode
toggle, the firewall helper and server status.

The router is built with the M21 networking collaborators wired to a
temp data dir. Mutations are loopback-only, mirroring pairing admin.
"""

import pytest

from paios.api.routes import ApiRouter
from paios.system import network


@pytest.fixture
def net_router(api_app, tmp_path):
    data_dir = tmp_path / "net-data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return ApiRouter(
        api_app,
        network_dir=data_dir,
        bound_host="127.0.0.1",
        bound_port=8765,
    )


def ok(router, method, path, body=None, expect=200, **context):
    status, payload = router.handle(method, path, body, **context)
    assert status == expect, payload
    return payload


class TestNetworkFacts:
    def test_get_network_reports_facts(self, net_router):
        payload = ok(net_router, "GET", "/system/network")
        assert payload["mode"] == "local"
        assert payload["port"] == 8765
        assert payload["lan_url"].startswith("http://")
        assert "firewall_rule" in payload
        assert payload["lan_reachable"] is False

    def test_server_status_proves_running(self, net_router):
        payload = ok(net_router, "GET", "/system/server")
        assert payload["running"] is True
        assert payload["port"] == 8765
        assert payload["mode"] == "local"
        assert "server_time" in payload

    def test_uncomposed_network_is_503(self, api_app):
        bare = ApiRouter(api_app)
        status, _ = bare.handle("GET", "/system/network")
        assert status == 503


class TestModeToggle:
    def test_switch_to_lan_persists_and_notes_restart(
        self, net_router, tmp_path
    ):
        payload = ok(
            net_router, "PUT", "/system/network", {"mode": "lan"}
        )
        assert payload["mode"] == "lan"
        assert payload["lan_reachable"] is True
        assert "restart" in payload["note"].lower()
        # Persisted where the server reads it at (re)start.
        assert (
            network.load_settings(tmp_path / "net-data")["mode"] == "lan"
        )

    def test_switch_back_to_local(self, net_router):
        ok(net_router, "PUT", "/system/network", {"mode": "lan"})
        payload = ok(
            net_router, "PUT", "/system/network", {"mode": "local"}
        )
        assert payload["mode"] == "local"

    def test_unknown_mode_rejected(self, net_router):
        status, _ = net_router.handle(
            "PUT", "/system/network", {"mode": "internet"}
        )
        assert status == 400

    def test_mode_change_is_loopback_only(self, net_router):
        status, _ = net_router.handle(
            "PUT", "/system/network", {"mode": "lan"},
            client_host="192.168.1.50",
        )
        assert status == 403
        # And a phone cannot open the firewall either.
        status, _ = net_router.handle(
            "POST", "/system/network/firewall", None,
            client_host="192.168.1.50",
        )
        assert status == 403


class TestDiscovery:
    def test_discovery_off_by_default(self, net_router):
        payload = ok(net_router, "GET", "/system/discovery")
        assert payload["advertising"] is False
        # And the network report reflects it.
        assert ok(net_router, "GET", "/system/network")["discovering"] is (
            False
        )

    def test_discovery_reports_active_advertiser(self, api_app, tmp_path):
        from paios.system.discovery import DiscoveryAdvertiser, ServiceInfo

        class Fake(DiscoveryAdvertiser):
            @property
            def running(self):
                return True

        advertiser = Fake(
            ServiceInfo(port=8765, address="192.168.1.5", instance="PAIOS")
        )
        router = ApiRouter(
            api_app,
            network_dir=tmp_path / "d",
            bound_host="0.0.0.0",
            bound_port=8765,
            discovery=advertiser,
        )
        (tmp_path / "d").mkdir()
        payload = ok(router, "GET", "/system/discovery")
        assert payload["advertising"] is True
        assert payload["service"] == "_paios._tcp.local"
        assert payload["port"] == 8765


class TestServerAdvertises:
    def test_lan_mode_starts_and_stops_the_advertiser(
        self, tmp_path, monkeypatch
    ):
        import socket

        from paios.api import ApiConfig, ApiServer
        from paios.system import discovery, network

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        network.save_settings(data_dir, "lan")

        sent = []

        class FakeSocket:
            def sendto(self, data, addr):
                sent.append(data)

            def recvfrom(self, size):
                raise socket.timeout()

            def settimeout(self, timeout):
                pass

            def close(self):
                pass

        monkeypatch.setattr(discovery, "default_socket", lambda: FakeSocket())
        server = ApiServer(
            ApiConfig(host="127.0.0.1", port=0, data_dir=str(data_dir))
        )
        server.start()
        try:
            assert server._advertiser is not None
            assert server._advertiser.running is True
            assert sent  # an announcement went out on start
        finally:
            server.shutdown()
        assert server._advertiser is None

    def test_local_mode_does_not_advertise(self, tmp_path):
        from paios.api import ApiConfig, ApiServer

        data_dir = tmp_path / "data"
        data_dir.mkdir()  # default local mode
        server = ApiServer(
            ApiConfig(host="127.0.0.1", port=0, data_dir=str(data_dir))
        )
        server.start()
        try:
            assert server._advertiser is None
        finally:
            server.shutdown()


class TestFirewallHelper:
    def test_firewall_helper_returns_outcome(self, net_router, monkeypatch):
        monkeypatch.setattr(
            network,
            "add_firewall_rule",
            lambda port, *a, **k: {
                "ok": True,
                "elevation_required": False,
                "detail": f"opened {port}",
            },
        )
        payload = ok(net_router, "POST", "/system/network/firewall")
        assert payload["ok"] is True
        assert "8765" in payload["detail"]
