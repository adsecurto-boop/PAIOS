"""The install/uninstall step engine behind PAIOSSetup.exe.

Every step logs what it did to the install log (and the console), and
every machine-touching operation goes through a port:

    runner(command, **kwargs)  -> subprocess.run by default
    registry                   -> WindowsRegistry / NullRegistry / fake

The payload directory is what the build embeds into PAIOSSetup.exe:
one `paios-*.whl` wheel and (optionally) `PAIOS.exe`. Without a
payload the installer falls back to installing the source tree it was
started from — the development path, identical to install.ps1.
"""

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from paios_installer.registry import NullRegistry, WindowsRegistry

RUN_VALUE_NAME = "PAIOS"
TASK_NAME = "PAIOS Daemon"
SHORTCUT_NAME = "PAIOS.lnk"
START_MENU_FOLDER = "PAIOS"
MINIMUM_PYTHON = (3, 12)
PUBLISHER = "PAIOS Project"
#: Payload subdirectory carrying the self-contained application tree
#: (PAIOS.exe + _internal + PAIOSUpdater.exe + version.txt). When it is
#: present the installer copies files — no Python, venv or pip needed.
APP_PAYLOAD_DIR = "app"


def default_user_data_dir() -> Path:
    """%LOCALAPPDATA%\\PAIOS — where the product keeps database,
    settings, logs, memories and backups. Never inside Program Files,
    never removed by an upgrade."""
    base = os.environ.get("LOCALAPPDATA")
    return (Path(base) if base else Path.home() / ".paios") / "PAIOS"


class InstallerError(RuntimeError):
    """A step failed; the message says which and why."""


@dataclass(frozen=True)
class InstallOptions:
    install_dir: Path
    #: Directory holding the bundled wheel + PAIOS.exe (None = dev
    #: install from ``source_dir``).
    payload_dir: Path | None = None
    #: Source tree fallback when no payload is bundled.
    source_dir: Path | None = None
    with_gui: bool = True
    create_shortcuts: bool = True
    #: Start PAIOS.exe at logon via the HKCU Run key.
    register_startup: bool = True
    #: Also register the headless runtime as a logon Task Scheduler
    #: task (`paios daemon start`) — the "service" option.
    runtime_task: bool = False
    python: str = "python"
    #: Standalone installs: where user data lives (None -> default).
    user_data_dir: Path | None = None


class InstallLog:
    """Installer log: every line to the console and the log file."""

    def __init__(self, path: Path, echo=print) -> None:
        self._path = path
        self._echo = echo
        path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = open(path, "a", encoding="utf-8")

    @property
    def path(self) -> Path:
        return self._path

    def write(self, message: str) -> None:
        stamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        self._handle.write(f"{stamp} | {message}\n")
        self._handle.flush()
        try:
            self._echo(message)
        except UnicodeEncodeError:
            # A cp1252 console must never kill the installer; the log
            # file above already has the full message.
            self._echo(message.encode("ascii", "replace").decode("ascii"))

    def close(self) -> None:
        self._handle.close()


def default_runner(command, **kwargs):
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    return subprocess.run(command, **kwargs)


def desktop_dir() -> Path:
    return Path.home() / "Desktop"


def start_menu_dir() -> Path:
    if os.name == "nt":
        return (
            Path(os.environ.get("APPDATA", Path.home()))
            / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        )
    return Path.home() / ".local" / "share" / "applications"


def shortcut_script(link_path: Path, target: Path, workdir: Path) -> str:
    """The PowerShell that writes one .lnk (WScript.Shell COM)."""
    return (
        "$s = (New-Object -ComObject WScript.Shell)"
        f".CreateShortcut('{link_path}'); "
        f"$s.TargetPath = '{target}'; "
        f"$s.WorkingDirectory = '{workdir}'; "
        "$s.Description = 'PAIOS - Personal AI Operating System'; "
        "$s.Save()"
    )


class Installer:
    def __init__(
        self,
        options: InstallOptions,
        *,
        runner=default_runner,
        registry=None,
        log: InstallLog | None = None,
        desktop: Path | None = None,
        start_menu: Path | None = None,
    ) -> None:
        self.options = options
        self.runner = runner
        self.registry = registry if registry is not None else (
            WindowsRegistry() if os.name == "nt" else NullRegistry()
        )
        self.log = log or InstallLog(
            options.install_dir / "logs" / "paios-install.log"
        )
        self._desktop = desktop or desktop_dir()
        self._start_menu = start_menu or start_menu_dir()

    # --- derived paths -----------------------------------------------------

    @property
    def venv_dir(self) -> Path:
        return self.options.install_dir / "venv"

    @property
    def venv_python(self) -> Path:
        scripts = "Scripts" if os.name == "nt" else "bin"
        name = "python.exe" if os.name == "nt" else "python"
        return self.venv_dir / scripts / name

    @property
    def venv_paios(self) -> Path:
        scripts = "Scripts" if os.name == "nt" else "bin"
        name = "paios.exe" if os.name == "nt" else "paios"
        return self.venv_dir / scripts / name

    @property
    def launcher_exe(self) -> Path:
        return self.options.install_dir / "PAIOS.exe"

    @property
    def config_file(self) -> Path:
        return self.options.install_dir / "config" / "config.yaml"

    @property
    def app_payload(self) -> Path | None:
        """The self-contained application tree in the payload, if any."""
        if self.options.payload_dir is None:
            return None
        candidate = self.options.payload_dir / APP_PAYLOAD_DIR
        return candidate if candidate.is_dir() else None

    @property
    def standalone(self) -> bool:
        """True when the payload carries the bundled application — the
        consumer product path: copy files, no Python required."""
        return self.app_payload is not None

    @property
    def user_data_dir(self) -> Path:
        return (
            self.options.user_data_dir
            if self.options.user_data_dir is not None
            else default_user_data_dir()
        )

    # --- the run -----------------------------------------------------------

    def run(self) -> None:
        if self.standalone:
            steps = [
                ("Checking previous installation", self.detect_previous),
                ("Stopping running PAIOS", self.stop_running),
                ("Installing application files", self.install_app_tree),
                ("Preparing user data folders", self.create_user_data_layout),
                ("Creating shortcuts", self.create_shortcuts),
                ("Registering startup", self.register_startup),
                ("Registering uninstaller", self.register_uninstall_entry),
                ("Running health checks", self.standalone_health_check),
            ]
        else:
            steps = [
                ("Checking Python", self.check_python),
                ("Creating directories", self.create_layout),
                ("Creating virtual environment", self.create_venv),
                ("Installing PAIOS", self.install_package),
                ("Placing PAIOS.exe", self.place_launcher),
                ("Generating configuration", self.generate_config),
                ("Creating shortcuts", self.create_shortcuts),
                ("Registering startup", self.register_startup),
                ("Registering runtime task", self.register_runtime_task),
                ("Running health checks", self.health_check),
            ]
        self.log.write(f"PAIOS installer -> {self.options.install_dir}")
        for title, step in steps:
            self.log.write(f"* {title}...")
            try:
                step()
            except InstallerError as error:
                self.log.write(f"FAILED: {error}")
                raise
            except Exception as error:
                self.log.write(f"FAILED: {title}: {error}")
                raise InstallerError(f"{title} failed: {error}") from error
        self.log.write("PAIOS installed successfully.")

    # --- standalone steps (the consumer product path) ----------------------

    def installed_version(self) -> str | None:
        version_file = self.options.install_dir / "version.txt"
        try:
            # utf-8-sig: tolerate a BOM (PowerShell writes one).
            text = version_file.read_text(encoding="utf-8-sig").strip()
            return text or None
        except OSError:
            return None

    def payload_version(self) -> str | None:
        payload = self.app_payload
        if payload is None:
            return None
        try:
            text = (payload / "version.txt").read_text(
                encoding="utf-8-sig"
            ).strip()
            return text or None
        except OSError:
            return None

    def detect_previous(self) -> None:
        previous = self.installed_version()
        target = self.payload_version() or "unknown"
        if previous is None:
            self.log.write(f"  fresh installation (PAIOS {target})")
        else:
            self.log.write(
                f"  upgrading PAIOS {previous} -> {target}"
                " (user data is untouched)"
            )

    def stop_running(self) -> None:
        """Ask a running PAIOS to exit so its files can be replaced."""
        if not self.launcher_exe.is_file():
            self.log.write("  nothing running to stop")
            return
        try:
            self.runner([str(self.launcher_exe), "--stop"], timeout=60)
            self.log.write("  stop requested")
        except Exception as error:  # best effort; install proceeds
            self.log.write(f"  stop request failed (ignored): {error}")

    def install_app_tree(self) -> None:
        payload = self.app_payload
        assert payload is not None
        self.options.install_dir.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copytree(
                payload, self.options.install_dir, dirs_exist_ok=True
            )
        except OSError as error:
            raise InstallerError(
                f"copying application files failed: {error}. Close any"
                " running PAIOS and retry."
            ) from error
        self.log.write(
            f"  application installed to {self.options.install_dir}"
        )

    def create_user_data_layout(self) -> None:
        for name in ("config", "data", "logs", "backups"):
            (self.user_data_dir / name).mkdir(parents=True, exist_ok=True)
        self.log.write(f"  user data home: {self.user_data_dir}")

    def register_uninstall_entry(self) -> None:
        """The Add/Remove Programs entry: name, version, publisher,
        icon, uninstall command."""
        uninstaller = self.options.install_dir / "PAIOSUninstall.exe"
        uninstall_command = (
            f'"{uninstaller}"'
            if uninstaller.is_file()
            else f'"{self.launcher_exe}" --stop'
        )
        version = self.installed_version() or "0.0.0"
        self.registry.set_uninstall_entry(
            {
                "DisplayName": "PAIOS",
                "DisplayVersion": version,
                "Publisher": PUBLISHER,
                "InstallLocation": str(self.options.install_dir),
                "DisplayIcon": str(self.launcher_exe),
                "UninstallString": uninstall_command,
            }
        )
        self.log.write(f"  uninstall entry registered (v{version})")

    def standalone_health_check(self) -> None:
        result = self.runner([str(self.launcher_exe), "--version"])
        reported = (getattr(result, "stdout", "") or "").strip()
        if getattr(result, "returncode", 1) == 0 and reported:
            self.log.write(f"  PAIOS.exe reports version {reported}")
        else:
            # Reported, not fatal — matches the legacy health behavior.
            self.log.write("  (health check could not confirm the version)")

    # --- steps -------------------------------------------------------------

    def check_python(self) -> None:
        try:
            result = self.runner(
                [
                    self.options.python,
                    "-c",
                    "import sys; print('%d.%d' % sys.version_info[:2])",
                ]
            )
        except OSError as error:
            raise InstallerError(
                f"Python not found ({self.options.python!r}):"
                f" {error}. Install Python 3.12+ from python.org."
            ) from error
        if result.returncode != 0:
            raise InstallerError(
                f"Python check failed ({self.options.python!r})."
            )
        major, minor = (int(p) for p in result.stdout.strip().split("."))
        if (major, minor) < MINIMUM_PYTHON:
            raise InstallerError(
                f"Python {MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]}+ required,"
                f" found {major}.{minor}."
            )
        self.log.write(f"  Python {major}.{minor} OK")

    def create_layout(self) -> None:
        for name in ("config", "data", "logs", "backups"):
            (self.options.install_dir / name).mkdir(
                parents=True, exist_ok=True
            )

    def create_venv(self) -> None:
        if self.venv_python.is_file():
            self.log.write("  venv already present; reusing")
            return
        result = self.runner(
            [self.options.python, "-m", "venv", str(self.venv_dir)]
        )
        if result.returncode != 0:
            raise InstallerError(
                f"venv creation failed: {result.stderr or result.stdout}"
            )

    def _wheel(self) -> Path | None:
        if self.options.payload_dir is None:
            return None
        wheels = sorted(self.options.payload_dir.glob("paios-*.whl"))
        return wheels[-1] if wheels else None

    def install_package(self) -> None:
        wheel = self._wheel()
        if wheel is not None:
            spec = f"{wheel}[gui]" if self.options.with_gui else str(wheel)
        elif self.options.source_dir is not None:
            source = str(self.options.source_dir)
            spec = f"{source}[gui]" if self.options.with_gui else source
        else:
            raise InstallerError(
                "Nothing to install: no bundled wheel and no source tree."
            )
        self.log.write(f"  pip install {spec}")
        result = self.runner(
            [
                str(self.venv_python),
                "-m", "pip", "install", "--upgrade", "--quiet", spec,
            ]
        )
        if result.returncode != 0:
            raise InstallerError(
                f"pip install failed: {result.stderr or result.stdout}"
            )

    def place_launcher(self) -> None:
        if self.options.payload_dir is None:
            self.log.write("  no payload; PAIOS.exe not placed (dev install)")
            return
        bundled = self.options.payload_dir / "PAIOS.exe"
        if not bundled.is_file():
            self.log.write("  payload has no PAIOS.exe; skipped")
            return
        shutil.copy2(bundled, self.launcher_exe)
        self.log.write(f"  {self.launcher_exe}")
        # M20: the standalone auto-updater ships beside the launcher.
        bundled_updater = self.options.payload_dir / "PAIOSUpdater.exe"
        if bundled_updater.is_file():
            updater_target = self.options.install_dir / "PAIOSUpdater.exe"
            shutil.copy2(bundled_updater, updater_target)
            self.log.write(f"  {updater_target}")
        # M20: version.txt — the updater's fast installed-version probe.
        wheel = self._wheel()
        if wheel is not None:
            version = wheel.name.split("-")[1]
            (self.options.install_dir / "version.txt").write_text(
                version + "\n", encoding="utf-8"
            )
            self.log.write(f"  version.txt = {version}")

    def generate_config(self) -> None:
        if self.config_file.is_file():
            self.log.write("  configuration exists; kept")
            return
        # `paios init` (M16) generates the commented config and the
        # directory skeleton — run from the install root so relative
        # paths land inside the install.
        result = self.runner(
            [str(self.venv_paios), "init"],
            cwd=str(self.options.install_dir),
        )
        if result.returncode != 0 or not self.config_file.is_file():
            raise InstallerError(
                "configuration generation failed:"
                f" {getattr(result, 'stderr', '') or ''}"
            )
        self.log.write(f"  {self.config_file}")

    def _shortcut_target(self) -> Path:
        return (
            self.launcher_exe
            if self.launcher_exe.is_file()
            else self.venv_paios
        )

    def create_shortcuts(self) -> None:
        if not self.options.create_shortcuts:
            self.log.write("  skipped (disabled)")
            return
        target = self._shortcut_target()
        start_menu_folder = self._start_menu / START_MENU_FOLDER
        start_menu_folder.mkdir(parents=True, exist_ok=True)
        for link in (
            self._desktop / SHORTCUT_NAME,
            start_menu_folder / SHORTCUT_NAME,
        ):
            link.parent.mkdir(parents=True, exist_ok=True)
            script = shortcut_script(
                link, target, self.options.install_dir
            )
            result = self.runner(
                ["powershell", "-NoProfile", "-Command", script]
            )
            if result.returncode != 0:
                raise InstallerError(
                    f"shortcut creation failed for {link}:"
                    f" {result.stderr or result.stdout}"
                )
            self.log.write(f"  {link}")

    def register_startup(self) -> None:
        if not self.options.register_startup:
            self.log.write("  skipped (disabled)")
            return
        if not self.launcher_exe.is_file():
            self.log.write("  no PAIOS.exe; startup not registered")
            return
        self.registry.set_run_value(
            RUN_VALUE_NAME, f'"{self.launcher_exe}"'
        )
        self.log.write(f"  HKCU Run '{RUN_VALUE_NAME}' -> {self.launcher_exe}")

    def register_runtime_task(self) -> None:
        if not self.options.runtime_task:
            self.log.write("  skipped (not requested)")
            return
        command = (
            f'"{self.venv_paios}" --config "{self.config_file}"'
            " daemon start"
        )
        result = self.runner(
            [
                "schtasks", "/Create", "/F", "/SC", "ONLOGON",
                "/TN", TASK_NAME, "/TR", command,
            ]
        )
        if result.returncode != 0:
            raise InstallerError(
                f"scheduled task creation failed:"
                f" {result.stderr or result.stdout}"
            )
        self.log.write(f"  scheduled task '{TASK_NAME}' -> {command}")

    def health_check(self) -> None:
        result = self.runner(
            [
                str(self.venv_paios),
                "--config", str(self.config_file),
                "health",
            ]
        )
        for line in (result.stdout or "").splitlines():
            self.log.write(f"  {line}")
        if result.returncode != 0:
            # Health problems are reported, not fatal — matches
            # install.ps1's yellow warning.
            self.log.write("  (health reported problems)")


class Uninstaller:
    """Reverse of the installer; ``keep_data`` preserves data/backups
    inside a legacy install dir. ``remove_user_data`` additionally
    deletes the separate user data home (%LOCALAPPDATA%\\PAIOS) — only
    ever True after the user explicitly declined to keep their data."""

    def __init__(
        self,
        install_dir: Path,
        *,
        keep_data: bool = False,
        remove_user_data: bool = False,
        user_data_dir: Path | None = None,
        runner=default_runner,
        registry=None,
        log: InstallLog | None = None,
        desktop: Path | None = None,
        start_menu: Path | None = None,
        echo=print,
    ) -> None:
        self.install_dir = install_dir
        self.keep_data = keep_data
        self.remove_user_data = remove_user_data
        self.user_data_dir = (
            user_data_dir
            if user_data_dir is not None
            else default_user_data_dir()
        )
        self.runner = runner
        self.registry = registry if registry is not None else (
            WindowsRegistry() if os.name == "nt" else NullRegistry()
        )
        # The uninstall log cannot live in the directory being removed.
        self.log = log or InstallLog(
            Path(os.environ.get("TEMP", str(Path.home())))
            / "paios-uninstall.log",
            echo=echo,
        )
        self._desktop = desktop or desktop_dir()
        self._start_menu = start_menu or start_menu_dir()

    def run(self) -> None:
        self.log.write(f"PAIOS uninstaller -> {self.install_dir}")
        self.stop_launcher()
        self.remove_startup()
        self.remove_runtime_task()
        self.remove_shortcuts()
        self.remove_uninstall_entry()
        self.remove_install_dir()
        self.remove_user_data_dir()
        self.log.write("PAIOS uninstalled.")

    def stop_launcher(self, wait_seconds: int = 20, sleep=None) -> None:
        """Ask a running PAIOS to exit and wait (bounded) until its
        executable is replaceable. `PAIOS.exe --stop` resolves the real
        log directory itself — standalone installs keep logs in the
        user data home, so writing sentinels here would miss them."""
        import time as _time

        sleep = sleep if sleep is not None else _time.sleep
        launcher = self.install_dir / "PAIOS.exe"
        if launcher.is_file():
            try:
                self.runner([str(launcher), "--stop"], timeout=60)
                self.log.write("  stop requested")
            except Exception as error:
                self.log.write(f"  stop request failed (ignored): {error}")
            for _ in range(wait_seconds):
                if not self._locked(launcher):
                    break
                sleep(1)
        # Legacy layout: sentinels beside the install, best effort.
        for logs in (self.install_dir / "logs",):
            if logs.is_dir():
                (logs / "paios-launcher.stop").write_text(
                    "stop", encoding="utf-8"
                )
                (logs / "paios-daemon.stop").write_text(
                    "stop", encoding="utf-8"
                )
        self.log.write("  stop sentinels written")

    @staticmethod
    def _locked(path: Path) -> bool:
        """True while Windows still holds the executable open."""
        try:
            with open(path, "ab"):
                return False
        except OSError:
            return True

    def remove_startup(self) -> None:
        self.registry.delete_run_value(RUN_VALUE_NAME)
        self.log.write("  startup registration removed")

    def remove_uninstall_entry(self) -> None:
        self.registry.delete_uninstall_entry()
        self.log.write("  uninstall entry removed")

    def remove_runtime_task(self) -> None:
        self.runner(["schtasks", "/Delete", "/F", "/TN", TASK_NAME])
        self.log.write(f"  scheduled task '{TASK_NAME}' removed (if present)")

    def remove_shortcuts(self) -> None:
        (self._desktop / SHORTCUT_NAME).unlink(missing_ok=True)
        folder = self._start_menu / START_MENU_FOLDER
        if folder.is_dir():
            shutil.rmtree(folder, ignore_errors=True)
        self.log.write("  shortcuts removed")

    def remove_install_dir(self) -> None:
        if not self.install_dir.is_dir():
            return
        if self.keep_data:
            leftovers = []
            for entry in self.install_dir.iterdir():
                if entry.name in ("data", "backups"):
                    continue
                try:
                    if entry.is_dir():
                        shutil.rmtree(entry)
                    else:
                        entry.unlink(missing_ok=True)
                except OSError:
                    leftovers.append(entry.name)
            if leftovers:
                self.log.write(
                    "  some files are still in use and were left behind: "
                    + ", ".join(leftovers)
                    + " — delete the folder after PAIOS fully exits"
                )
            self.log.write("  install removed (data/backups kept)")
        else:
            shutil.rmtree(self.install_dir, ignore_errors=True)
            if self.install_dir.exists():
                self.log.write(
                    "  some files are still in use; delete "
                    f"{self.install_dir} after PAIOS fully exits"
                )
            self.log.write("  install directory removed")

    def remove_user_data_dir(self) -> None:
        """The separate user data home — deleted ONLY on an explicit
        "remove my data" choice, and never when it coincides with the
        install dir (legacy layout; handled by remove_install_dir)."""
        target = self.user_data_dir
        if not self.remove_user_data:
            if target.is_dir() and target != self.install_dir:
                self.log.write(f"  user data kept: {target}")
            return
        if target == self.install_dir or not target.is_dir():
            return
        shutil.rmtree(target, ignore_errors=True)
        self.log.write(f"  user data removed: {target}")
