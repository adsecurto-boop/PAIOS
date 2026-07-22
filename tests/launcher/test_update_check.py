"""Launcher update checks (M20): notify-only, resilient, hand-off."""

import json

from paios_launcher.update_check import (
    AvailableUpdate,
    UpdateChecker,
    check_interval_hours,
)
from paios_updater import releases


def feed(tag: str, installable: bool = True):
    assets = (
        [
            {"name": releases.SETUP_ASSET, "browser_download_url": "u1"},
            {"name": releases.CHECKSUMS_ASSET, "browser_download_url": "u2"},
        ]
        if installable
        else []
    )
    return lambda url: json.dumps(
        {"tag_name": tag, "body": "notes", "assets": assets}
    )


class TestUpdateChecker:
    def test_newer_installable_release_is_reported(self):
        checker = UpdateChecker(
            repo="o/r", fetcher=feed("v9.9.9"), current_version="2.2.0"
        )
        found = checker.check()
        assert found == AvailableUpdate(
            current="2.2.0", target="9.9.9", notes="notes"
        )
        assert checker.available == found

    def test_current_release_reports_nothing(self):
        checker = UpdateChecker(
            repo="o/r", fetcher=feed("v2.2.0"), current_version="2.2.0"
        )
        assert checker.check() is None
        assert checker.available is None

    def test_non_installable_release_ignored(self):
        checker = UpdateChecker(
            repo="o/r",
            fetcher=feed("v9.9.9", installable=False),
            current_version="2.2.0",
        )
        assert checker.check() is None

    def test_network_failure_never_raises(self):
        def broken(url):
            raise OSError("offline")

        checker = UpdateChecker(
            repo="o/r", fetcher=broken, current_version="2.2.0"
        )
        assert checker.check() is None

    def test_unknown_installed_version_skips(self):
        checker = UpdateChecker(
            repo="o/r", fetcher=feed("v9.9.9"), current_version=None
        )
        checker._current = None  # simulate missing metadata
        assert checker.check() is None


class TestInterval:
    def test_default_interval(self, monkeypatch):
        monkeypatch.delenv("PAIOS_UPDATE_INTERVAL_HOURS", raising=False)
        assert check_interval_hours() == 24.0

    def test_env_override_and_garbage(self, monkeypatch):
        monkeypatch.setenv("PAIOS_UPDATE_INTERVAL_HOURS", "6")
        assert check_interval_hours() == 6.0
        monkeypatch.setenv("PAIOS_UPDATE_INTERVAL_HOURS", "-1")
        assert check_interval_hours() == 24.0
        monkeypatch.setenv("PAIOS_UPDATE_INTERVAL_HOURS", "soon")
        assert check_interval_hours() == 24.0
