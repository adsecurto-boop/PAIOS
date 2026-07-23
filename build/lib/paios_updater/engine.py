"""The update engine: check -> download -> verify -> stop -> backup ->
install -> health check -> restart, with rollback from the backup on
any post-backup failure.

Every side effect goes through an injectable collaborator (downloader,
process runner), so the whole pipeline is provable with fakes. The
engine never imports paios: it stops/starts the app by invoking
PAIOS.exe and asks the install's own venv Python for the installed
version — process boundaries, not imports.
"""

import json
import os
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from paios_updater import checksums, releases, versions

_DOWNLOAD_TIMEOUT_SECONDS = 300
_STOP_TIMEOUT_SECONDS = 60
_INSTALL_TIMEOUT_SECONDS = 900


class UpdateError(Exception):
    """A pipeline failure. `rolled_back` records whether the previous
    installation was restored."""

    def __init__(self, message: str, rolled_back: bool = False) -> None:
        super().__init__(message)
        self.rolled_back = rolled_back


@dataclass(frozen=True)
class UpdatePlan:
    """What `check` found: everything `apply` needs, immutable."""

    current_version: str
    target_version: str
    notes: str
    setup_url: str
    checksums_url: str


@dataclass
class UpdaterConfig:
    install_dir: Path
    repo: str = releases.DEFAULT_REPO
    current_version: str | None = None  # None -> read from the install

    @property
    def launcher_exe(self) -> Path:
        return self.install_dir / "PAIOS.exe"

    @property
    def version_file(self) -> Path:
        return self.install_dir / "version.txt"

    @property
    def backup_root(self) -> Path:
        return self.install_dir / "backups" / "updates"


def default_downloader(url: str, target: Path) -> None:
    request = urllib.request.Request(
        url, headers={"User-Agent": "PAIOSUpdater"}
    )
    with urllib.request.urlopen(
        request, timeout=_DOWNLOAD_TIMEOUT_SECONDS
    ) as reply, open(target, "wb") as handle:
        shutil.copyfileobj(reply, handle)


def default_runner(command: list[str], timeout: int) -> int:
    completed = subprocess.run(
        command, capture_output=True, text=True, timeout=timeout
    )
    return completed.returncode


@dataclass
class UpdateEngine:
    config: UpdaterConfig
    fetcher: object = field(default=releases.default_fetcher)
    downloader: object = field(default=default_downloader)
    runner: object = field(default=default_runner)
    log: object = field(default=print)

    # --- check --------------------------------------------------------------

    def installed_version(self) -> str:
        """version.txt when present (fast path, written by installs and
        updates), else PAIOS.exe's own answer (standalone installs),
        else the install venv's answer (legacy installs)."""
        if self.config.current_version:
            return self.config.current_version
        if self.config.version_file.is_file():
            text = self.config.version_file.read_text(
                encoding="utf-8-sig"
            ).strip()
            if text:
                return text
        reported = self._launcher_reported_version()
        if reported is not None:
            return reported
        python = self._venv_python()
        if python is not None:
            try:
                completed = subprocess.run(
                    [
                        str(python), "-c",
                        "import importlib.metadata as m;"
                        "print(m.version('paios'))",
                    ],
                    capture_output=True, text=True, timeout=30,
                )
                if completed.returncode == 0 and completed.stdout.strip():
                    return completed.stdout.strip()
            except (OSError, subprocess.TimeoutExpired):
                pass
        raise UpdateError(
            f"Cannot determine the installed version under "
            f"{self.config.install_dir}"
        )

    def check(self) -> UpdatePlan | None:
        """None when already current; an UpdatePlan when an installable
        newer release exists."""
        current = self.installed_version()
        release = releases.latest_release(self.config.repo, self.fetcher)
        self.log(f"installed {current}; latest release {release.tag}")
        if not versions.is_newer(release.tag, current):
            return None
        if not release.installable:
            raise UpdateError(
                f"Release {release.tag} is missing "
                f"{releases.SETUP_ASSET} or {releases.CHECKSUMS_ASSET}"
            )
        return UpdatePlan(
            current_version=current,
            target_version=release.tag.lstrip("v"),
            notes=release.notes,
            setup_url=release.assets[releases.SETUP_ASSET],
            checksums_url=release.assets[releases.CHECKSUMS_ASSET],
        )

    # --- apply ---------------------------------------------------------------

    def apply(self, plan: UpdatePlan) -> None:
        """Run the full pipeline for a checked plan. Raises UpdateError;
        after the backup point failures roll the installation back."""
        staging = Path(tempfile.mkdtemp(prefix="paios-update-"))
        setup = staging / releases.SETUP_ASSET
        sums = staging / releases.CHECKSUMS_ASSET
        self.log(f"downloading {plan.setup_url}")
        self.downloader(plan.setup_url, setup)
        self.downloader(plan.checksums_url, sums)
        checksums.verify(setup, sums.read_text(encoding="utf-8"))
        self.log("checksum verified")

        self._stop_paios()
        backup = self._backup(plan.current_version)
        self.log(f"backup: {backup}")
        try:
            # One silent command line drives both installer flavors:
            # Inno Setup honors the switches, the console installer
            # tolerates and ignores them.
            code = self.runner(
                [
                    str(setup),
                    "/VERYSILENT", "/SUPPRESSMSGBOXES",
                    "/NORESTART", "/CLOSEAPPLICATIONS",
                ],
                _INSTALL_TIMEOUT_SECONDS,
            )
            if code != 0:
                raise UpdateError(f"Installer exited with code {code}")
            installed = self._post_install_version()
            if installed != plan.target_version:
                raise UpdateError(
                    f"Health check failed: installed {installed!r}, "
                    f"expected {plan.target_version!r}"
                )
            self.config.version_file.write_text(
                plan.target_version + "\n", encoding="utf-8"
            )
        except UpdateError:
            self._rollback(backup)
            raise UpdateError(
                "Update failed; previous installation restored",
                rolled_back=True,
            )
        except Exception as error:
            self._rollback(backup)
            raise UpdateError(
                f"Update failed ({error}); previous installation restored",
                rolled_back=True,
            ) from error
        finally:
            shutil.rmtree(staging, ignore_errors=True)

        self.log(f"updated to {plan.target_version}; restarting PAIOS")
        self._restart_paios()

    # --- steps ----------------------------------------------------------------

    def _stop_paios(self) -> None:
        if not self.config.launcher_exe.is_file():
            return  # nothing installed to stop
        try:
            self.runner(
                [str(self.config.launcher_exe), "--stop"],
                _STOP_TIMEOUT_SECONDS,
            )
        except Exception:
            pass  # not running is fine; the installer replaces files

    def _backup(self, current_version: str) -> Path:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.config.backup_root.mkdir(parents=True, exist_ok=True)
        target = self.config.backup_root / f"update-{stamp}.zip"
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            if self.config.launcher_exe.is_file():
                archive.write(self.config.launcher_exe, "PAIOS.exe")
            internal = self.config.install_dir / "_internal"
            if internal.is_dir():  # standalone (onedir) application
                for item in internal.rglob("*"):
                    if item.is_file():
                        archive.write(
                            item,
                            Path("_internal")
                            / item.relative_to(internal),
                        )
            for tree in self._paios_package_dirs():
                for item in tree.rglob("*"):
                    if item.is_file():
                        archive.write(
                            item,
                            Path("site-packages")
                            / item.relative_to(tree.parent),
                        )
            archive.writestr(
                "manifest.json",
                json.dumps(
                    {"previous_version": current_version, "created": stamp}
                ),
            )
        return target

    def _rollback(self, backup: Path) -> None:
        self.log("rolling back from backup")
        site_packages = self._site_packages()
        if site_packages is not None:
            for tree in self._paios_package_dirs():
                shutil.rmtree(tree, ignore_errors=True)
        with zipfile.ZipFile(backup) as archive:
            names = archive.namelist()
            if any(name.startswith("_internal/") for name in names):
                shutil.rmtree(
                    self.config.install_dir / "_internal",
                    ignore_errors=True,
                )
            for name in names:
                if name == "PAIOS.exe":
                    archive.extract(name, self.config.install_dir)
                elif name.startswith("_internal/"):
                    archive.extract(name, self.config.install_dir)
                elif name.startswith("site-packages/") and (
                    site_packages is not None
                ):
                    relative = Path(name).relative_to("site-packages")
                    destination = site_packages / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(name) as source, open(
                        destination, "wb"
                    ) as target:
                        shutil.copyfileobj(source, target)

    def _launcher_reported_version(self) -> str | None:
        """`PAIOS.exe --version` — the standalone install's own answer
        (and a liveness proof: the freshly installed binary must run)."""
        if not self.config.launcher_exe.is_file():
            return None
        try:
            completed = subprocess.run(
                [str(self.config.launcher_exe), "--version"],
                capture_output=True, text=True, timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        text = (completed.stdout or "").strip()
        if completed.returncode != 0 or not text or text == "unknown":
            return None
        return text

    def _post_install_version(self) -> str:
        # Never trust a stale version.txt for the health check — ask the
        # install itself: the standalone launcher first (proves the new
        # binary starts), then the legacy venv query.
        reported = self._launcher_reported_version()
        if reported is not None:
            return reported
        probe = UpdaterConfig(
            install_dir=self.config.install_dir, repo=self.config.repo
        )
        engine = UpdateEngine(
            config=probe, fetcher=self.fetcher,
            downloader=self.downloader, runner=self.runner, log=self.log,
        )
        probe_file = probe.version_file
        if probe_file.is_file():
            probe_file.unlink()  # force the venv query below
        return engine.installed_version()

    def _restart_paios(self) -> None:
        if not self.config.launcher_exe.is_file():
            return
        creation_flags = 0
        if os.name == "nt":  # detach: the updater must be free to exit
            creation_flags = 0x00000008  # DETACHED_PROCESS
        subprocess.Popen(
            [str(self.config.launcher_exe)],
            creationflags=creation_flags,
            close_fds=True,
        )

    # --- install layout helpers -------------------------------------------------

    def _venv_python(self) -> Path | None:
        for candidate in (
            self.config.install_dir / "venv" / "Scripts" / "python.exe",
            self.config.install_dir / "venv" / "bin" / "python",
        ):
            if candidate.is_file():
                return candidate
        return None

    def _site_packages(self) -> Path | None:
        windows = self.config.install_dir / "venv" / "Lib" / "site-packages"
        if windows.is_dir():
            return windows
        posix = self.config.install_dir / "venv" / "lib"
        if posix.is_dir():
            for python_dir in sorted(posix.glob("python*")):
                candidate = python_dir / "site-packages"
                if candidate.is_dir():
                    return candidate
        return None

    def _paios_package_dirs(self) -> list[Path]:
        site_packages = self._site_packages()
        if site_packages is None:
            return []
        return [
            item
            for item in sorted(site_packages.glob("paios*"))
            if item.is_dir()
        ]
