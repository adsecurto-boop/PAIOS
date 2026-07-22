"""Periodic update checks for PAIOS.exe (Milestone 20).

The launcher only ever CHECKS and NOTIFIES — installing is entirely
PAIOSUpdater.exe's job (a separate process the user approves; the
launcher exits so the updater can replace it). Imports are confined to
paios_updater's pure modules (release lookup, semver) — no Runtime, no
Scheduler, no paios.* at all in this module.
"""

import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from paios_updater import releases, versions

logger = logging.getLogger("paios.launcher.updates")

#: How often the tray re-checks. Overridable for tests/ops.
DEFAULT_INTERVAL_HOURS = 24.0


def check_interval_hours() -> float:
    raw = os.environ.get("PAIOS_UPDATE_INTERVAL_HOURS")
    try:
        value = float(raw) if raw else DEFAULT_INTERVAL_HOURS
    except ValueError:
        value = DEFAULT_INTERVAL_HOURS
    return value if value > 0 else DEFAULT_INTERVAL_HOURS


def installed_version() -> str | None:
    """The running product's version, from package metadata."""
    try:
        from importlib.metadata import version

        return version("paios")
    except Exception:  # pragma: no cover - metadata always present installed
        return None


@dataclass(frozen=True)
class AvailableUpdate:
    current: str
    target: str
    notes: str


class UpdateChecker:
    """One check() per interval tick; remembers the last finding so the
    tray can offer "Install update" until it is acted on."""

    def __init__(
        self,
        repo: str | None = None,
        fetcher=releases.default_fetcher,
        current_version: str | None = None,
    ) -> None:
        self._repo = repo or os.environ.get(
            "PAIOS_UPDATE_REPO", releases.DEFAULT_REPO
        )
        self._fetcher = fetcher
        self._current = current_version or installed_version()
        self.available: AvailableUpdate | None = None

    def check(self) -> AvailableUpdate | None:
        """Never raises — a failed check logs and reports nothing (the
        launcher must keep running through network trouble)."""
        if not self._current:
            logger.info("update check skipped: unknown installed version")
            return None
        try:
            release = releases.latest_release(self._repo, self._fetcher)
            if release.installable and versions.is_newer(
                release.tag, self._current
            ):
                self.available = AvailableUpdate(
                    current=self._current,
                    target=release.tag.lstrip("v"),
                    notes=release.notes,
                )
                logger.info(
                    "update available: %s -> %s",
                    self._current, self.available.target,
                )
                return self.available
            self.available = None
        except (releases.ReleaseError, versions.VersionError) as error:
            logger.info("update check failed: %s", error)
        return self.available


def updater_executable(install_root: Path) -> Path | None:
    candidate = install_root / "PAIOSUpdater.exe"
    return candidate if candidate.is_file() else None


def launch_updater(install_root: Path) -> bool:
    """Spawn PAIOSUpdater.exe detached (installed) or the module in
    development. Returns True when something was launched — the caller
    then exits so the updater can replace PAIOS.exe."""
    executable = updater_executable(install_root)
    command: list[str]
    if executable is not None:
        command = [str(executable), "--yes"]
    else:
        command = [sys.executable, "-m", "paios_updater", "--yes"]
    creation_flags = 0x00000008 if os.name == "nt" else 0  # DETACHED_PROCESS
    try:
        subprocess.Popen(command, creationflags=creation_flags, close_fds=True)
        return True
    except OSError as error:
        logger.error("cannot launch updater: %s", error)
        return False
