"""Local networking facts and helpers for the Networking page (M21).

Stdlib only, best-effort, never raises: every probe degrades to a safe
default so the GUI can always render a Networking page. All the OS
queries take an injectable runner so the whole module is unit-testable
with no real network, no real firewall and no admin rights.

Two responsibilities:

    1. Read-only facts — LAN IP, Wi-Fi SSID, firewall-rule presence,
       the loopback and LAN URLs — behind one ``report()`` call the
       REST layer serializes directly.
    2. The persisted access mode — "local" (loopback only, the safe
       default) or "lan" (reachable by paired phones on the same
       Wi-Fi). The mode lives in ``network-settings.json`` beside the
       other data files; the API bind host is resolved from it at
       server (re)start, so the GUI toggle needs no terminal and no
       environment variables.
"""

import json
import socket
import subprocess
from pathlib import Path

FILE_NAME = "network-settings.json"

#: The Windows Firewall inbound rule PAIOS manages for LAN access.
FIREWALL_RULE_NAME = "PAIOS API"

LOOPBACK_HOST = "127.0.0.1"
ANY_HOST = "0.0.0.0"

_MODES = ("local", "lan")
_QUERY_TIMEOUT_SECONDS = 4


# --- persisted access mode --------------------------------------------------


def settings_path(data_dir: Path | str) -> Path:
    return Path(data_dir) / FILE_NAME


def load_settings(data_dir: Path | str) -> dict:
    """The stored network settings, or the safe default (local mode).
    Never raises — a missing or corrupt file reads as loopback-only."""
    try:
        payload = json.loads(settings_path(data_dir).read_text("utf-8"))
    except (OSError, ValueError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    mode = payload.get("mode")
    return {"mode": mode if mode in _MODES else "local"}


def save_settings(data_dir: Path | str, mode: str) -> dict:
    """Persist the access mode. Unknown modes fall back to 'local' —
    the mode never silently becomes something unsafe."""
    normalized = mode if mode in _MODES else "local"
    target = settings_path(data_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"mode": normalized}, indent=2, sort_keys=True), "utf-8"
    )
    return {"mode": normalized}


def host_for_mode(mode: str) -> str:
    """Bind host for a mode: LAN binds every interface, local is
    loopback only (the default whenever the mode is unknown)."""
    return ANY_HOST if mode == "lan" else LOOPBACK_HOST


def mode_for_host(host: str) -> str:
    return "lan" if host in (ANY_HOST, "::", "") else "local"


def resolve_bind_host(data_dir: Path | str, configured_host: str) -> str:
    """The host the API should bind to: the persisted LAN choice wins
    over the configured host (so the GUI toggle takes effect), but a
    'local' setting never overrides an explicitly LAN-configured host."""
    if load_settings(data_dir)["mode"] == "lan":
        return ANY_HOST
    return configured_host


# --- read-only facts --------------------------------------------------------


def hostname() -> str:
    try:
        return socket.gethostname()
    except OSError:
        return "this-computer"


def local_ip(connector=None) -> str:
    """The machine's primary LAN IPv4 address (the one a phone on the
    same Wi-Fi would reach), or 127.0.0.1 when offline. No packets are
    sent — connecting a UDP socket only selects a route.

    ``connector`` is injectable for tests: a callable returning the
    address string, or raising to simulate no network."""
    if connector is not None:
        try:
            return connector()
        except OSError:
            return LOOPBACK_HOST
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        return probe.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return LOOPBACK_HOST
    finally:
        probe.close()


def _run(runner, command: list[str]):
    """Run a system query; return (returncode, stdout) or (None, "")
    when the tool is absent or times out."""
    run = runner if runner is not None else subprocess.run
    kwargs = {
        "capture_output": True,
        "text": True,
        "timeout": _QUERY_TIMEOUT_SECONDS,
    }
    if subprocess.os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = startupinfo
    try:
        completed = run(command, **kwargs)
    except (OSError, subprocess.TimeoutExpired):
        return None, ""
    return completed.returncode, completed.stdout or ""


def wifi_ssid(runner=None) -> str | None:
    """The connected Wi-Fi network name (Windows, via netsh), or None
    on Ethernet, without Wi-Fi, or on other platforms."""
    code, output = _run(runner, ["netsh", "wlan", "show", "interfaces"])
    if code != 0:
        return None
    for line in output.splitlines():
        key, separator, value = line.partition(":")
        name = key.strip().lower()
        if separator and name == "ssid":  # skip 'BSSID'
            ssid = value.strip()
            return ssid or None
    return None


def firewall_rule_present(runner=None, rule_name: str = FIREWALL_RULE_NAME):
    """Whether the PAIOS inbound firewall rule exists.

    Returns True/False on Windows, or None where the firewall cannot be
    queried (non-Windows, netsh absent) — the UI then shows 'unknown'
    rather than a false 'blocked'."""
    code, output = _run(
        runner,
        [
            "netsh", "advfirewall", "firewall", "show", "rule",
            f"name={rule_name}",
        ],
    )
    if code is None:
        return None
    if code != 0:
        return False
    return "no rules match" not in output.lower()


def add_firewall_rule(
    port: int, runner=None, rule_name: str = FIREWALL_RULE_NAME
) -> dict:
    """Add the inbound TCP allow rule so paired phones can reach the API
    on the LAN. Adding a firewall rule needs administrator rights; when
    that is missing this returns ``elevation_required`` with a plain
    instruction rather than failing silently."""
    code, output = _run(
        runner,
        [
            "netsh", "advfirewall", "firewall", "add", "rule",
            f"name={rule_name}", "dir=in", "action=allow",
            "protocol=TCP", f"localport={int(port)}",
        ],
    )
    if code is None:
        return {
            "ok": False,
            "elevation_required": False,
            "detail": "The Windows firewall tool is not available on this"
            " system; no change was made.",
        }
    if code == 0:
        return {
            "ok": True,
            "elevation_required": False,
            "detail": f"Firewall now allows incoming connections on port"
            f" {int(port)}.",
        }
    lowered = output.lower()
    elevation = (
        "requires elevation" in lowered
        or "access is denied" in lowered
        or "run as administrator" in lowered
    )
    return {
        "ok": False,
        "elevation_required": elevation,
        "detail": (
            "Opening the firewall needs administrator rights. Right-click"
            " PAIOS and choose 'Run as administrator', then try again."
            if elevation
            else (output.strip() or "The firewall rule could not be added.")
        ),
    }


def urls(ip: str, port: int) -> dict:
    return {
        "loopback_url": f"http://{LOOPBACK_HOST}:{int(port)}",
        "lan_url": f"http://{ip}:{int(port)}",
    }


def report(
    data_dir: Path | str,
    configured_host: str,
    port: int,
    *,
    connector=None,
    runner=None,
) -> dict:
    """Everything the Networking page renders, in one shape.

    ``configured_host`` is the host the running server was told to bind;
    the effective mode is derived from the persisted setting so the page
    reflects the choice even before the next restart applies it."""
    settings = load_settings(data_dir)
    mode = settings["mode"]
    ip = local_ip(connector)
    firewall = firewall_rule_present(runner)
    return {
        "hostname": hostname(),
        "lan_ip": ip,
        "port": int(port),
        "mode": mode,
        "configured_host": configured_host,
        "bound_host": host_for_mode(mode),
        "lan_reachable": mode == "lan",
        "wifi_ssid": wifi_ssid(runner),
        "firewall_rule": firewall,
        "firewall_rule_name": FIREWALL_RULE_NAME,
        **urls(ip, port),
    }
