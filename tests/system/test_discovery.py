"""mDNS / DNS-SD advertising (M22).

The wire encoding is checked against the DNS message format byte-for-
byte; the advertiser is driven through an injected fake socket, so no
multicast traffic and no real network are involved.
"""

import socket
import struct
import time

import pytest

from paios.system import discovery
from paios.system.discovery import DiscoveryAdvertiser, ServiceInfo


@pytest.fixture
def info():
    return ServiceInfo(
        port=8765,
        address="192.168.1.5",
        instance="PAIOS on LAPTOP",
        hostname="laptop",
        properties={"server": "paios", "path": "/mobile"},
    )


# --- wire format ------------------------------------------------------------


class TestEncoding:
    def test_encode_name_matches_dns_label_format(self):
        assert discovery.encode_name("_paios._tcp.local") == (
            b"\x06_paios\x04_tcp\x05local\x00"
        )

    def test_encode_name_root_is_single_zero(self):
        assert discovery.encode_name("") == b"\x00"

    def test_encode_txt_key_values(self):
        encoded = discovery.encode_txt({"server": "paios"})
        assert encoded == b"\x0cserver=paios"

    def test_encode_txt_empty_is_single_empty_string(self):
        assert discovery.encode_txt({}) == b"\x00"

    def test_response_header_counts(self, info):
        packet = discovery.build_response(info)
        tid, flags, qd, an, ns, ar = struct.unpack("!HHHHHH", packet[:12])
        assert flags == 0x8400  # response + authoritative
        assert qd == 0 and an == 1  # the PTR is the single answer
        assert ar == 3  # SRV + TXT + A ride as additionals

    def test_response_carries_port_and_address(self, info):
        packet = discovery.build_response(info)
        assert struct.pack("!H", 8765) in packet  # SRV port
        assert socket.inet_aton("192.168.1.5") in packet  # A record
        assert b"_paios" in packet


class TestQueryParsing:
    def _ptr_query(self, name: str) -> bytes:
        header = struct.pack("!HHHHHH", 0x1234, 0, 1, 0, 0, 0)
        return header + discovery.encode_name(name) + struct.pack("!HH", 12, 1)

    def test_question_names_extracts_the_query(self):
        query = self._ptr_query("_paios._tcp.local")
        assert discovery.question_names(query) == [
            ("_paios._tcp.local", 12)
        ]

    def test_malformed_query_yields_no_questions(self):
        assert discovery.question_names(b"\x00\x01") == []

    def test_should_respond_to_service_browse(self, info):
        assert discovery.should_respond(
            self._ptr_query("_paios._tcp.local"), info
        )

    def test_should_ignore_other_services(self, info):
        assert not discovery.should_respond(
            self._ptr_query("_spotify._tcp.local"), info
        )


# --- advertiser lifecycle ---------------------------------------------------


class FakeSocket:
    def __init__(self, queries=()):
        self.sent = []
        self.closed = False
        self._queries = list(queries)

    def sendto(self, data, addr):
        self.sent.append(data)

    def recvfrom(self, size):
        if self._queries:
            return self._queries.pop(0), (discovery.MDNS_ADDRESS, 5353)
        raise socket.timeout()

    def settimeout(self, timeout):
        pass

    def close(self):
        self.closed = True


class TestAdvertiser:
    def test_start_announces_then_stop_closes(self, info):
        fake = FakeSocket()
        advertiser = DiscoveryAdvertiser(info, socket_factory=lambda: fake)
        assert advertiser.start() is True
        assert advertiser.running is True
        assert fake.sent  # an unsolicited announcement went out
        assert fake.sent[0] == discovery.build_response(info)
        advertiser.stop()
        assert advertiser.running is False
        assert fake.closed is True

    def test_answers_a_browse_query(self, info):
        query = (
            struct.pack("!HHHHHH", 0, 0, 1, 0, 0, 0)
            + discovery.encode_name("_paios._tcp.local")
            + struct.pack("!HH", 12, 1)
        )
        fake = FakeSocket(queries=[query])
        advertiser = DiscoveryAdvertiser(info, socket_factory=lambda: fake)
        advertiser.start()
        deadline = time.monotonic() + 2.0
        while len(fake.sent) < 2 and time.monotonic() < deadline:
            time.sleep(0.02)
        advertiser.stop()
        # Announcement + at least one query reply, both the full record.
        assert len(fake.sent) >= 2
        assert all(
            packet == discovery.build_response(info) for packet in fake.sent
        )

    def test_start_is_best_effort_when_socket_fails(self, info):
        def boom():
            raise OSError("mDNS port busy")

        advertiser = DiscoveryAdvertiser(info, socket_factory=boom)
        assert advertiser.start() is False
        assert advertiser.running is False
