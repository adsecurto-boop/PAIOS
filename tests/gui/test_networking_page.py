"""The Networking page (M21) against a live server.

The live server is loopback and running, so the page shows a running
server in Local Only mode; switching to Local Network must persist and
repaint. The firewall button is NOT exercised here (it would change the
real firewall) — that path is covered by unit + API tests with fakes.
"""

import pytest

from paios_gui.networking_page import NetworkingPage


@pytest.fixture
def page(window):
    widget = NetworkingPage(window)
    widget.refresh(window.client)
    return widget


def port_of(base_url: str) -> str:
    return base_url.rsplit(":", 1)[-1].rstrip("/")


class TestRender:
    def test_facts_show_port_and_ip(self, page, window):
        assert page._value_labels["port"].text() == port_of(
            window.client.base_url
        )
        assert page._value_labels["lan_ip"].text() not in ("", "—")

    def test_starts_in_local_only_mode(self, page):
        assert page.mode_chip.text() == "Local Only"
        assert "Local Only" in page.access_hint.text()
        # In local mode the address the phone would use is the loopback.
        assert page.address_label.text().startswith("http://127.0.0.1")

    def test_discovery_chip_off_in_local_mode(self, page):
        assert page.discovery_chip.text() == "Discovery: off"

    def test_running_server_is_detected(self, page):
        # The live server answers, so the controller reports running.
        assert "running" in page.server_chip.text().lower()
        assert not page.start_button.isEnabled()


class TestModeToggle:
    def test_switch_to_local_network_persists_and_repaints(
        self, page, window
    ):
        page._on_set_mode("lan")
        page.refresh(window.client)
        assert page.mode_chip.text() == "Local Network"
        # The offered address is now the LAN URL.
        assert not page.address_label.text().startswith("http://127.0.0.1")
        # And the server agrees over REST.
        assert window.client.system_network()["mode"] == "lan"

    def test_switch_back_to_local(self, page, window):
        page._on_set_mode("lan")
        page.refresh(window.client)
        page._on_set_mode("local")
        page.refresh(window.client)
        assert page.mode_chip.text() == "Local Only"


class TestRemoteAccess:
    def test_remote_section_defaults_off(self, page):
        assert page.remote_chip.text() == "Off"
        assert page.remote_enable.isChecked() is False

    def test_paint_relay_states(self, page):
        page._paint_relay({"enabled": False})
        assert page.remote_chip.text() == "Off"
        page._paint_relay({"enabled": True, "connected": True})
        assert page.remote_chip.text() == "Connected"
        page._paint_relay({"enabled": True, "last_error": "boom"})
        assert page.remote_chip.text() == "Disconnected"
        page._paint_relay({"enabled": True})
        assert page.remote_chip.text() == "Connecting…"

    def test_save_relay_persists_config(self, page, window):
        # Save with remote disabled (no connector spawned) but a URL set;
        # the settings must round-trip through the server.
        page.relay_url_edit.setText("https://relay.example.com")
        page.relay_account_edit.setText("me")
        page.remote_enable.setChecked(False)
        page._on_save_relay()
        relay = window.client.system_relay()
        assert relay["relay_url"] == "https://relay.example.com"
        assert relay["account"] == "me"
        assert relay["enabled"] is False

    def test_enabling_without_url_is_refused(self, page):
        page.relay_url_edit.setText("")
        page.remote_enable.setChecked(True)
        page._on_save_relay()  # must not raise; notifies instead
        # Still off on the server.
        assert page._window.client.system_relay()["enabled"] is False


class TestAddress:
    def test_qr_toggles_on_and_off(self, page):
        assert page.qr_label.isHidden()
        page._on_toggle_qr()
        assert not page.qr_label.isHidden()
        assert not page.qr_label.pixmap().isNull()
        page._on_toggle_qr()
        assert page.qr_label.isHidden()

    def test_copy_address_does_not_raise(self, page):
        page._on_copy_address()  # clipboard set; must not raise offscreen
