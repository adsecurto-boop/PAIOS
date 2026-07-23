"""Zero-config LAN discovery (M22): the desktop advertises PAIOS over
mDNS / DNS-SD so a phone on the same Wi-Fi finds it with no typed IP.

Stdlib only — a small, focused mDNS *responder* for one service type,
``_paios._tcp.local``. It answers browse (PTR) and resolve (SRV/TXT/A)
queries and sends unsolicited announcements when it starts, which is
exactly what Android's NsdManager and Apple's Bonjour need to list and
resolve the service. It does not implement the full multicast-DNS
conflict/goodbye machinery — advertising one cooperative service is all
PAIOS needs, and everything degrades quietly (no raised exceptions) so
discovery never destabilises the server.

The wire encoding is pure functions (fully unit-tested against the DNS
message format); the socket wiring is a thin, best-effort thread.
"""

import socket
import struct
import threading
from dataclasses import dataclass, field

MDNS_ADDRESS = "224.0.0.251"
MDNS_PORT = 5353
SERVICE_TYPE = "_paios._tcp.local"
DEFAULT_TTL = 120

# DNS record types and classes.
_TYPE_A = 1
_TYPE_PTR = 12
_TYPE_TXT = 16
_TYPE_SRV = 33
_TYPE_ANY = 255
_CLASS_IN = 0x0001
#: IN with the mDNS cache-flush bit — used on the unique SRV/TXT/A
#: records (never on the shared PTR).
_CLASS_FLUSH = 0x8001


@dataclass(frozen=True)
class ServiceInfo:
    """One advertised PAIOS instance."""

    port: int
    address: str  # the LAN IPv4 to resolve to
    instance: str = "PAIOS"  # human label shown while browsing
    hostname: str = "paios"  # <hostname>.local A record
    properties: dict = field(default_factory=dict)  # TXT key/values

    @property
    def instance_name(self) -> str:
        return f"{self.instance}.{SERVICE_TYPE}"

    @property
    def host_name(self) -> str:
        return f"{self.hostname}.local"


# --- DNS wire format (pure) -------------------------------------------------


def encode_name(name: str) -> bytes:
    """A DNS name as length-prefixed labels ending in a zero byte.
    ``_paios._tcp.local`` -> b'\\x06_paios\\x04_tcp\\x05local\\x00'."""
    out = bytearray()
    for label in name.split("."):
        if not label:
            continue
        encoded = label.encode("utf-8")
        if len(encoded) > 63:
            raise ValueError(f"DNS label too long: {label!r}")
        out.append(len(encoded))
        out.extend(encoded)
    out.append(0)
    return bytes(out)


def encode_txt(properties: dict) -> bytes:
    """DNS-SD TXT rdata: each 'key=value' as a length-prefixed string.
    Empty properties encode as a single empty string (RFC 6763 §6.1)."""
    if not properties:
        return b"\x00"
    out = bytearray()
    for key, value in properties.items():
        entry = f"{key}={value}".encode("utf-8")[:255]
        out.append(len(entry))
        out.extend(entry)
    return bytes(out)


def _record(
    name: str, rtype: int, rclass: int, ttl: int, rdata: bytes
) -> bytes:
    return (
        encode_name(name)
        + struct.pack("!HHIH", rtype, rclass, ttl, len(rdata))
        + rdata
    )


def _srv_rdata(info: ServiceInfo) -> bytes:
    # priority 0, weight 0, then the port and the target host name.
    return struct.pack("!HHH", 0, 0, info.port) + encode_name(info.host_name)


def answer_records(info: ServiceInfo, ttl: int = DEFAULT_TTL) -> list[bytes]:
    """The four records that fully describe the service: PTR (browse),
    then SRV + TXT + A (resolve), in the order a client consumes them."""
    return [
        _record(
            SERVICE_TYPE, _TYPE_PTR, _CLASS_IN, ttl,
            encode_name(info.instance_name),
        ),
        _record(
            info.instance_name, _TYPE_SRV, _CLASS_FLUSH, ttl,
            _srv_rdata(info),
        ),
        _record(
            info.instance_name, _TYPE_TXT, _CLASS_FLUSH, ttl,
            encode_txt(info.properties),
        ),
        _record(
            info.host_name, _TYPE_A, _CLASS_FLUSH, ttl,
            socket.inet_aton(info.address),
        ),
    ]


def build_response(info: ServiceInfo, ttl: int = DEFAULT_TTL) -> bytes:
    """A full mDNS response: the PTR as the answer, SRV/TXT/A as
    additionals so one packet both lists and resolves the service.
    Used for both announcements and query replies."""
    records = answer_records(info, ttl)
    header = struct.pack(
        "!HHHHHH",
        0,            # transaction id (0 in mDNS)
        0x8400,       # flags: response + authoritative
        0,            # questions
        1,            # answers: the PTR
        0,            # authority
        len(records) - 1,  # additionals: SRV, TXT, A
    )
    return header + b"".join(records)


def _read_name(data: bytes, offset: int) -> int:
    """Advance past a DNS name (handles compression pointers); returns
    the offset after the name. We only need the cursor, not the text."""
    while offset < len(data):
        length = data[offset]
        if length == 0:
            return offset + 1
        if length & 0xC0 == 0xC0:  # compression pointer: two bytes, done
            return offset + 2
        offset += 1 + length
    return offset


def question_names(query: bytes) -> list[tuple[str, int]]:
    """(name, qtype) for each question in a query — best-effort, returns
    [] on any malformed packet (a responder never trusts the wire)."""
    try:
        if len(query) < 12:
            return []
        qdcount = struct.unpack("!H", query[4:6])[0]
        offset = 12
        questions: list[tuple[str, int]] = []
        for _ in range(qdcount):
            labels = []
            cursor = offset
            while cursor < len(query):
                length = query[cursor]
                if length == 0:
                    cursor += 1
                    break
                if length & 0xC0 == 0xC0:
                    cursor += 2
                    break
                labels.append(
                    query[cursor + 1: cursor + 1 + length].decode(
                        "utf-8", "replace"
                    )
                )
                cursor += 1 + length
            qtype = struct.unpack("!H", query[cursor: cursor + 2])[0]
            questions.append((".".join(labels), qtype))
            offset = cursor + 4  # past qtype + qclass
        return questions
    except (struct.error, IndexError):
        return []


def should_respond(query: bytes, info: ServiceInfo) -> bool:
    """True when a query asks about our service type, our instance, or
    our host — the cases a browsing/resolving phone sends."""
    wanted = {
        SERVICE_TYPE.lower(),
        info.instance_name.lower(),
        info.host_name.lower(),
    }
    for name, qtype in question_names(query):
        if qtype in (_TYPE_PTR, _TYPE_SRV, _TYPE_TXT, _TYPE_A, _TYPE_ANY):
            if name.lower() in wanted:
                return True
    return False


# --- the advertiser (thin, best-effort socket thread) -----------------------


def default_socket() -> socket.socket:
    """A socket joined to the mDNS multicast group. Best-effort socket
    options: platforms differ, and discovery must never be fatal."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    for option in ("SO_REUSEPORT",):
        try:
            sock.setsockopt(
                socket.SOL_SOCKET, getattr(socket, option), 1
            )
        except (AttributeError, OSError):
            pass
    sock.bind(("", MDNS_PORT))
    membership = struct.pack(
        "4sl", socket.inet_aton(MDNS_ADDRESS), socket.INADDR_ANY
    )
    sock.setsockopt(
        socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership
    )
    try:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
    except OSError:
        pass
    sock.settimeout(1.0)
    return sock


class DiscoveryAdvertiser:
    """Advertise a ServiceInfo over mDNS until stopped. The socket is
    injectable so the responder loop is tested with no real network."""

    def __init__(self, info: ServiceInfo, socket_factory=None):
        self._info = info
        # Resolved at start() time (not bound here) so the module-level
        # default_socket stays monkeypatchable in tests.
        self._socket_factory = socket_factory
        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._running = threading.Event()

    @property
    def running(self) -> bool:
        return self._running.is_set()

    @property
    def info(self) -> ServiceInfo:
        return self._info

    def start(self) -> bool:
        """Open the socket, announce once, and serve queries in a
        background thread. Returns False (never raises) when the socket
        cannot be opened — discovery is optional, the server goes on."""
        if self._running.is_set():
            return True
        factory = (
            self._socket_factory
            if self._socket_factory is not None
            else default_socket
        )
        try:
            self._socket = factory()
        except OSError:
            self._socket = None
            return False
        self._running.set()
        self._announce()
        self._thread = threading.Thread(
            target=self._serve, name="paios-mdns", daemon=True
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        self._running.clear()
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def _announce(self) -> None:
        self._send(build_response(self._info))

    def _send(self, payload: bytes) -> None:
        if self._socket is None:
            return
        try:
            self._socket.sendto(payload, (MDNS_ADDRESS, MDNS_PORT))
        except OSError:
            pass

    def _serve(self) -> None:
        while self._running.is_set() and self._socket is not None:
            try:
                query, _ = self._socket.recvfrom(9000)
            except socket.timeout:
                continue
            except OSError:
                break
            if should_respond(query, self._info):
                self._send(build_response(self._info))
