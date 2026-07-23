"""Networking facts and the persisted access mode (M21).

Every OS probe is exercised through an injected fake runner/connector,
so these tests touch no real network, firewall or Wi-Fi and pass on any
platform.
"""

import subprocess

from paios.system import network


class FakeCompleted:
    def __init__(self, returncode: int, stdout: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = ""


def runner_returning(returncode: int, stdout: str = ""):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return FakeCompleted(returncode, stdout)

    run.calls = calls
    return run


# --- persisted access mode --------------------------------------------------


class TestAccessMode:
    def test_default_is_local_when_absent(self, tmp_path):
        assert network.load_settings(tmp_path)["mode"] == "local"

    def test_save_and_load_roundtrip(self, tmp_path):
        network.save_settings(tmp_path, "lan")
        assert network.load_settings(tmp_path)["mode"] == "lan"

    def test_unknown_mode_falls_back_to_local(self, tmp_path):
        network.save_settings(tmp_path, "public-internet")
        assert network.load_settings(tmp_path)["mode"] == "local"

    def test_corrupt_file_reads_as_local(self, tmp_path):
        network.settings_path(tmp_path).write_text("{bad", encoding="utf-8")
        assert network.load_settings(tmp_path)["mode"] == "local"

    def test_host_for_mode(self):
        assert network.host_for_mode("lan") == network.ANY_HOST
        assert network.host_for_mode("local") == network.LOOPBACK_HOST
        assert network.host_for_mode("nonsense") == network.LOOPBACK_HOST

    def test_resolve_bind_host_lan_overrides_configured(self, tmp_path):
        network.save_settings(tmp_path, "lan")
        assert (
            network.resolve_bind_host(tmp_path, "127.0.0.1")
            == network.ANY_HOST
        )

    def test_resolve_bind_host_local_keeps_configured(self, tmp_path):
        network.save_settings(tmp_path, "local")
        assert network.resolve_bind_host(tmp_path, "192.168.1.9") == (
            "192.168.1.9"
        )


# --- LAN IP -----------------------------------------------------------------


class TestLocalIp:
    def test_uses_injected_connector(self):
        assert network.local_ip(connector=lambda: "192.168.1.42") == (
            "192.168.1.42"
        )

    def test_falls_back_to_loopback_when_offline(self):
        def offline():
            raise OSError("network is unreachable")

        assert network.local_ip(connector=offline) == network.LOOPBACK_HOST

    def test_real_probe_returns_an_ipv4_string(self):
        ip = network.local_ip()
        assert ip.count(".") == 3


# --- Wi-Fi SSID -------------------------------------------------------------


class TestWifi:
    def test_parses_ssid_and_skips_bssid(self):
        output = (
            "    Name                   : Wi-Fi\n"
            "    BSSID                  : aa:bb:cc:dd:ee:ff\n"
            "    SSID                   : HomeNetwork\n"
        )
        assert network.wifi_ssid(runner_returning(0, output)) == (
            "HomeNetwork"
        )

    def test_none_when_netsh_fails(self):
        assert network.wifi_ssid(runner_returning(1, "")) is None

    def test_none_when_tool_absent(self):
        def missing(command, **kwargs):
            raise FileNotFoundError("netsh not found")

        assert network.wifi_ssid(missing) is None


# --- firewall ---------------------------------------------------------------


class TestFirewall:
    def test_rule_present_true(self):
        run = runner_returning(0, "Rule Name: PAIOS API\nEnabled: Yes\n")
        assert network.firewall_rule_present(run) is True

    def test_rule_absent_no_match(self):
        run = runner_returning(1, "No rules match the specified criteria.")
        assert network.firewall_rule_present(run) is False

    def test_rule_unknown_when_tool_absent(self):
        def missing(command, **kwargs):
            raise FileNotFoundError

        assert network.firewall_rule_present(missing) is None

    def test_add_rule_success(self):
        run = runner_returning(0, "Ok.")
        result = network.add_firewall_rule(8765, run)
        assert result["ok"] is True
        assert "8765" in result["detail"]
        assert "localport=8765" in " ".join(run.calls[0])

    def test_add_rule_needs_elevation(self):
        run = runner_returning(
            1, "The requested operation requires elevation."
        )
        result = network.add_firewall_rule(8765, run)
        assert result["ok"] is False
        assert result["elevation_required"] is True
        assert "administrator" in result["detail"].lower()

    def test_add_rule_reports_missing_tool(self):
        def missing(command, **kwargs):
            raise FileNotFoundError

        result = network.add_firewall_rule(8765, missing)
        assert result["ok"] is False
        assert result["elevation_required"] is False


# --- one-call report --------------------------------------------------------


class TestReport:
    def test_report_shape_in_local_mode(self, tmp_path):
        payload = network.report(
            tmp_path,
            "127.0.0.1",
            8765,
            connector=lambda: "192.168.1.5",
            runner=runner_returning(1, "No rules match"),
        )
        assert payload["mode"] == "local"
        assert payload["lan_ip"] == "192.168.1.5"
        assert payload["port"] == 8765
        assert payload["bound_host"] == network.LOOPBACK_HOST
        assert payload["lan_reachable"] is False
        assert payload["lan_url"] == "http://192.168.1.5:8765"
        assert payload["loopback_url"] == "http://127.0.0.1:8765"
        assert payload["firewall_rule"] is False

    def test_report_shape_in_lan_mode(self, tmp_path):
        network.save_settings(tmp_path, "lan")
        payload = network.report(
            tmp_path,
            "0.0.0.0",
            8765,
            connector=lambda: "192.168.1.5",
            runner=runner_returning(0, "Rule Name: PAIOS API"),
        )
        assert payload["mode"] == "lan"
        assert payload["bound_host"] == network.ANY_HOST
        assert payload["lan_reachable"] is True
        assert payload["firewall_rule"] is True

    def test_report_uses_real_subprocess_by_default(self, tmp_path):
        # No runner injected: must not raise even where netsh is absent.
        payload = network.report(tmp_path, "127.0.0.1", 8765)
        assert payload["port"] == 8765
        assert "lan_url" in payload
