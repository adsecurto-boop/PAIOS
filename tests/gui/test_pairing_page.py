"""The pairing page (M21 enhancement): a generated code now comes with
a connection address, a QR of it, and a live expiry countdown."""

import pytest

from paios_gui.pages import MobileDevicesPage


@pytest.fixture
def page(window):
    return MobileDevicesPage(window)


class TestGenerate:
    def test_generate_shows_code_qr_and_countdown(self, page):
        page.on_generate()
        assert "Pairing code" in page.code_label.text()
        assert not page.code_label.isHidden()
        assert not page.qr_label.isHidden()
        assert not page.qr_label.pixmap().isNull()
        assert not page.countdown_label.isHidden()
        assert page.countdown_label.text().startswith("Expires in 5:")

    def test_hint_carries_the_server_address(self, page):
        page.on_generate()
        assert "server address" in page.code_hint.text().lower()
        assert "http://" in page.code_hint.text()

    def test_local_only_mode_warns_phone_cannot_reach(self, page, window):
        # The live server starts in Local Only mode.
        page.on_generate()
        assert "local only" in page.code_hint.text().lower()

    def test_lan_mode_has_no_warning(self, page, window):
        window.client.set_network_mode("lan")
        page.on_generate()
        assert "local only" not in page.code_hint.text().lower()


class TestCountdown:
    def test_countdown_ticks_down(self, page):
        page.on_generate()
        page._tick_countdown()
        assert page.countdown_label.text() == "Expires in 4:59"

    def test_countdown_expiry_hides_code(self, page):
        page.on_generate()
        page._remaining = 1
        page._tick_countdown()
        assert "expired" in page.countdown_label.text().lower()
        assert page.code_label.isHidden()
