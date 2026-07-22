"""PAIOS.exe assembly: config -> guard -> supervisor -> tray/loop.

Frozen by PyInstaller into PAIOS.exe (scripts/build_installer.py) and
installed as the `paios-launcher` console script for development. The
children are the M16 public command surfaces run with the *product's*
Python — inside an install that is `<install>\\venv\\Scripts\\python.exe`
(PAIOS_PYTHON, written by the installer), in development it is the
current interpreter.

File protocol (all in the log directory, matching the M16 daemon
runner conventions):

    paios-launcher.lock   single-instance guard (non-Windows / tests;
                          Windows uses a named mutex)
    paios-launcher.stop   sentinel: a headless launcher exits when it
                          appears (`PAIOS.exe --stop` creates it)
    paios-daemon.stop     M16 sentinel the daemon child honours between
                          ticks — the launcher's graceful pre-stop hook
    paios-<child>.out     raw child stdout/stderr
    crashes/              one report per unexpected child death
"""

import argparse
import logging
import os
import sys
import time
import traceback
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from paios.system.config import SystemConfig, load_system_config
from paios.system.logs import setup_logging

from paios_launcher.single_instance import (
    AlreadyRunningError,
    SingleInstance,
)
from paios_launcher.supervisor import ChildSpec, Supervisor

logger = logging.getLogger("paios.launcher")


# --- environment resolution -------------------------------------------------


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def install_dir() -> Path:
    """The directory PAIOS.exe lives in (the install root), or the
    repository root equivalent in development (the working directory)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def child_python() -> str:
    """The interpreter the children run with: PAIOS_PYTHON (installer)
    > the install's venv > this interpreter (development)."""
    override = os.environ.get("PAIOS_PYTHON")
    if override:
        return override
    venv_python = install_dir() / "venv" / "Scripts" / "python.exe"
    if venv_python.is_file():
        return str(venv_python)
    if is_frozen():
        # Frozen without a venv: nothing sensible to run children with.
        raise FileNotFoundError(
            f"No product Python found ({venv_python} missing and"
            " PAIOS_PYTHON not set) — reinstall PAIOS."
        )
    return sys.executable


def resolve_config(explicit_path: str | None) -> SystemConfig:
    """flag > $PAIOS_CONFIG > <install>/config/config.yaml > defaults;
    without a config file, logs nest in the data dir (the M16 rule)."""
    if explicit_path is None and not os.environ.get("PAIOS_CONFIG"):
        candidate = install_dir() / "config" / "config.yaml"
        if candidate.is_file():
            explicit_path = str(candidate)
    system = load_system_config(explicit_path)
    if system.source is None:
        system = replace(
            system, log_dir=str(Path(system.data_dir) / "logs")
        )
    return system


# --- composition ------------------------------------------------------------


def stop_sentinel(system: SystemConfig) -> Path:
    return Path(system.log_dir) / "paios-launcher.stop"


def lock_path(system: SystemConfig) -> Path:
    return Path(system.log_dir) / "paios-launcher.lock"


def crash_dir(system: SystemConfig) -> Path:
    return Path(system.log_dir) / "crashes"


def build_specs(
    system: SystemConfig,
    python: str,
    *,
    with_gui: bool = True,
) -> list[ChildSpec]:
    log_dir = Path(system.log_dir)
    config_args = (
        ("--config", system.source) if system.source is not None else ()
    )
    daemon_stop = log_dir / "paios-daemon.stop"

    def request_daemon_stop() -> None:
        daemon_stop.parent.mkdir(parents=True, exist_ok=True)
        daemon_stop.write_text("stop", encoding="utf-8")

    url = f"http://{system.server_host}:{system.server_port}"
    specs = [
        ChildSpec(
            name="daemon",
            command=(python, "-m", "paios.cli", *config_args,
                     "daemon", "run"),
            pre_stop=request_daemon_stop,
            output_path=log_dir / "paios-daemon.out",
        ),
        ChildSpec(
            name="api",
            command=(python, "-m", "paios.cli", *config_args, "serve"),
            output_path=log_dir / "paios-api.out",
        ),
    ]
    if with_gui:
        specs.append(
            ChildSpec(
                name="gui",
                command=(
                    python, "-m", "paios_gui",
                    "--url", url,
                    "--refresh", str(system.gui_refresh_seconds),
                    "--log-dir", system.log_dir,
                ),
                output_path=log_dir / "paios-gui.out",
            )
        )
    return specs


def build_supervisor(
    system: SystemConfig, specs: list[ChildSpec]
) -> Supervisor:
    def log_event(event) -> None:
        logger.info(
            "child=%s event=%s%s",
            event.child,
            event.kind,
            f" {event.detail}" if event.detail else "",
        )

    return Supervisor(specs, crash_dir=crash_dir(system), on_event=log_event)


def install_crash_hook(system: SystemConfig) -> None:
    """The launcher's own unhandled exceptions become crash reports."""

    def hook(exc_type, exc_value, exc_tb) -> None:
        try:
            directory = crash_dir(system)
            directory.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            report = directory / f"paios-crash-launcher-{stamp}.log"
            report.write_text(
                "".join(
                    traceback.format_exception(exc_type, exc_value, exc_tb)
                ),
                encoding="utf-8",
            )
            logger.error("launcher crashed: %s", exc_value)
        finally:
            sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = hook


# --- run modes --------------------------------------------------------------


def run_headless(
    supervisor: Supervisor,
    sentinel: Path,
    *,
    poll_interval: float = 1.0,
    max_polls: int | None = None,
    sleep=time.sleep,
) -> int:
    """Supervision loop without a tray: poll until the stop sentinel
    appears, Ctrl+C arrives, or (tests) max_polls is reached."""
    sentinel.unlink(missing_ok=True)
    supervisor.start_all()
    polls = 0
    try:
        while True:
            supervisor.poll()
            polls += 1
            if sentinel.exists():
                logger.info("stop sentinel found; shutting down")
                break
            if max_polls is not None and polls >= max_polls:
                break
            sleep(poll_interval)
    except KeyboardInterrupt:
        logger.info("interrupted; shutting down")
    finally:
        supervisor.shutdown()
        sentinel.unlink(missing_ok=True)
    return 0


class TrayController:
    """Bridges tray menu intents to the supervisor (and the desktop)."""

    def __init__(
        self,
        supervisor: Supervisor,
        system: SystemConfig,
        app,
        update_checker=None,
    ) -> None:
        self._supervisor = supervisor
        self._system = system
        self._app = app
        # M20: injected checker (None in tests keeps the tray silent).
        self._update_checker = update_checker
        self.on_update_available = None  # tray hook, set by run_tray

    # --- updates (M20: check + notify only; installing is the updater's job)

    def check_for_updates(self) -> None:
        if self._update_checker is None:
            return
        found = self._update_checker.check()
        if found is not None and self.on_update_available is not None:
            self.on_update_available(found)

    def update_available(self):
        if self._update_checker is None:
            return None
        return self._update_checker.available

    def install_update(self) -> None:
        """Hand over to PAIOSUpdater.exe and exit — the updater stops,
        replaces and restarts PAIOS; the launcher must not linger."""
        from paios_launcher.update_check import launch_updater

        if launch_updater(install_dir()):
            logger.info("updater launched; exiting for file replacement")
            self._app.quit()

    def overall_state(self) -> str:
        return self._supervisor.overall_state()

    def status(self) -> dict:
        return self._supervisor.status()

    def open_dashboard(self) -> None:
        status = self._supervisor.status()
        if "gui" in status and status["gui"]["state"] != "running":
            self._supervisor.resume("gui")
        elif "gui" not in status:
            import webbrowser

            webbrowser.open(
                f"http://{self._system.server_host}"
                f":{self._system.server_port}"
            )

    def pause_runtime(self) -> None:
        self._supervisor.pause("daemon")

    def resume_runtime(self) -> None:
        self._supervisor.resume("daemon")

    def restart_runtime(self) -> None:
        self._supervisor.restart("daemon")

    def view_logs(self) -> None:
        directory = str(Path(self._system.log_dir))
        if sys.platform == "win32":
            os.startfile(directory)  # noqa: attribute exists on Windows
        else:
            import webbrowser

            webbrowser.open(f"file://{directory}")

    def quit(self) -> None:
        self._app.quit()


def run_tray(supervisor: Supervisor, system: SystemConfig) -> int:
    """Supervision under a Qt event loop with the tray as the UI."""
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    from paios_launcher.tray import LauncherTray
    from paios_launcher.update_check import UpdateChecker, check_interval_hours

    controller = TrayController(
        supervisor, system, app, update_checker=UpdateChecker()
    )
    tray = LauncherTray(controller)
    controller.on_update_available = tray.notify_update_available
    poll_timer = QTimer()
    poll_timer.setInterval(1000)
    poll_timer.timeout.connect(supervisor.poll)
    # M20: periodic update check — notify only; installing stays a
    # user-approved tray action that launches PAIOSUpdater.exe.
    update_timer = QTimer()
    update_timer.setInterval(int(check_interval_hours() * 3600 * 1000))
    update_timer.timeout.connect(controller.check_for_updates)

    supervisor.start_all()
    tray.refresh()
    if LauncherTray.isSystemTrayAvailable():
        tray.show()
    tray.start_monitoring()
    poll_timer.start()
    update_timer.start()
    # First check shortly after boot, off the startup path.
    QTimer.singleShot(15_000, controller.check_for_updates)
    try:
        return_code = app.exec()
    finally:
        update_timer.stop()
        poll_timer.stop()
        tray.stop_monitoring()
        tray.hide()
        supervisor.shutdown()
    return return_code


# --- entry ------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="PAIOS", description="PAIOS product launcher"
    )
    parser.add_argument("--config", default=None, help="config.yaml path")
    parser.add_argument(
        "--no-tray", action="store_true",
        help="run headless (no Qt); stop via Ctrl+C or --stop",
    )
    parser.add_argument(
        "--no-gui", action="store_true",
        help="do not start the desktop dashboard child",
    )
    parser.add_argument(
        "--stop", action="store_true",
        help="ask a running headless launcher to shut down",
    )
    parser.add_argument(
        "--version", action="store_true",
        help="print the installed PAIOS version and exit (M20: the "
        "updater's health-check hook)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_arg_parser().parse_args(
        sys.argv[1:] if argv is None else argv
    )
    if arguments.version:
        from paios_launcher.update_check import installed_version

        print(installed_version() or "unknown")
        return 0
    try:
        system = resolve_config(arguments.config)
    except (FileNotFoundError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    setup_logging(system.log_dir, "launcher")
    install_crash_hook(system)

    if arguments.stop:
        sentinel = stop_sentinel(system)
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text("stop", encoding="utf-8")
        print("Stop requested; the launcher will exit shortly.")
        return 0

    # PAIOS_LAUNCHER_MUTEX lets tests (and parallel dev sandboxes) use
    # a private guard instead of colliding with a real running PAIOS.
    guard = SingleInstance(
        name=os.environ.get(
            "PAIOS_LAUNCHER_MUTEX", "PAIOS.Launcher.SingleInstance"
        ),
        lock_file=None if os.name == "nt" else lock_path(system),
    )
    try:
        guard.acquire()
    except AlreadyRunningError as error:
        logger.info("second instance refused: %s", error)
        print(f"{error}", file=sys.stderr)
        return 2

    try:
        python = child_python()
    except FileNotFoundError as error:
        guard.release()
        logger.error("%s", error)
        print(f"Error: {error}", file=sys.stderr)
        return 1

    specs = build_specs(system, python, with_gui=not arguments.no_gui)
    supervisor = build_supervisor(system, specs)
    logger.info(
        "launcher starting (pid %s, python %s, config %s)",
        os.getpid(), python, system.source or "defaults",
    )
    try:
        if arguments.no_tray:
            return run_headless(supervisor, stop_sentinel(system))
        return run_tray(supervisor, system)
    finally:
        guard.release()
        logger.info("launcher stopped")


if __name__ == "__main__":
    raise SystemExit(main())
