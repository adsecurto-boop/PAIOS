"""QR rendering for pairing / networking (M21).

The matrix and ASCII forms need no Qt; the pixmap needs a QApplication.
Encoding correctness is segno's; these tests pin the shapes the pages
rely on.
"""

from paios_gui import qr


class TestMatrix:
    def test_matrix_is_square_and_boolean(self):
        rows = qr.matrix("http://192.168.1.5:8765")
        assert len(rows) == len(rows[0])
        assert all(isinstance(cell, bool) for cell in rows[0])

    def test_finder_pattern_top_left(self):
        # Every QR has a 7x7 finder: a solid border ring at each corner.
        rows = qr.matrix("http://192.168.1.5:8765")
        assert all(rows[0][c] for c in range(7))  # top edge of finder
        assert all(rows[r][0] for r in range(7))  # left edge of finder
        assert not rows[5][5]  # the ring's inner gap

    def test_longer_input_needs_a_larger_symbol(self):
        small = len(qr.matrix("http://10.0.0.2:8765"))
        big = len(qr.matrix("http://10.0.0.2:8765/" + "x" * 120))
        assert big > small


class TestAscii:
    def test_ascii_has_dark_modules_and_quiet_zone(self):
        art = qr.ascii_art("http://192.168.1.5:8765")
        assert "█" in art
        lines = art.splitlines()
        assert lines[0].strip() == ""  # quiet zone on top


class TestConnectionUri:
    def test_lan_only_returns_plain_url(self):
        assert qr.connection_uri(lan_url="http://192.168.1.5:8765") == (
            "http://192.168.1.5:8765"
        )

    def test_relay_produces_versioned_pairing_uri(self):
        uri = qr.connection_uri(
            lan_url="http://192.168.1.5:8765",
            relay_url="https://relay.example.com",
            account="me",
        )
        assert uri.startswith("paios://pair?")
        assert "lan=http://192.168.1.5:8765" in uri
        assert "relay=https://relay.example.com" in uri
        assert "account=me" in uri

    def test_relay_only_omits_lan(self):
        uri = qr.connection_uri(relay_url="https://relay.example.com")
        assert "lan=" not in uri and "relay=" in uri

    def test_nothing_returns_empty(self):
        assert qr.connection_uri() == ""


class TestPixmap:
    def test_pixmap_is_non_empty(self, qapp):
        image = qr.pixmap("http://192.168.1.5:8765", module_pixels=4)
        assert not image.isNull()
        assert image.width() > 0 and image.width() == image.height()
