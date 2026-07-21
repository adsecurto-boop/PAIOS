"""Process-level daemon management around the M9 RuntimeDaemon.

The M9 daemon owns the loop; this runner owns the PROCESS: PID file,
foreground run with graceful Ctrl+C, detached background start, stop
via a sentinel file (portable graceful shutdown — no signals needed on
Windows), restart, and status. The RuntimeDaemon itself is untouched;
its `run_until(predicate)` seam is where the stop file and the backup
policy are checked between ticks.

Files (in the log directory, the process-state home):
    paios-daemon.pid    the background daemon's process id
    paios-daemon.stop   created by `paios daemon stop`; the running
                        daemon exits cleanly when it appears
"""

import os
import subprocess
import sys
import time
from pathlib import Path

from paios.application.application import Application
from paios.application.config import ApplicationConfig
from paios.daemon.config import DaemonConfig
from paios.daemon.daemon import RuntimeDaemon
from paios.system.backup import BackupManager, BackupPolicy
from paios.system.config import SystemConfig

def pid_file(config: SystemConfig) -> Path:
    return Path(config.log_dir) / "paios-daemon.pid"


def stop_file(config: SystemConfig) -> Path:
    return Path(config.log_dir) / "paios-daemon.stop"


# --- process liveness (Windows-first, POSIX fallback) ----------------------


def process_alive(pid: int) -> bool:
    if os.name == "nt":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def read_pid(config: SystemConfig) -> int | None:
    path = pid_file(config)
    if not path.is_file():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


# --- foreground ------------------------------------------------------------


def run_foreground(
    config: SystemConfig,
    build_observers=None,
    max_iterations: int | None = None,
    output=None,
) -> int:
    """Run the daemon loop in this process until Ctrl+C, the stop file,
    or (for tests) max_iterations. Owns the Application lifecycle.

    ``build_observers(application)`` lets the composition root attach
    bus observers (logging, notifications) once the bus exists."""
    out = output if output is not None else sys.stdout
    stop_marker = stop_file(config)
    stop_marker.unlink(missing_ok=True)
    Path(config.log_dir).mkdir(parents=True, exist_ok=True)
    pid_path = pid_file(config)
    pid_path.write_text(str(os.getpid()), encoding="utf-8")

    application = Application(ApplicationConfig(data_dir=config.data_dir))
    application.start()
    detach = None
    if build_observers is not None:
        detach = build_observers(application)
    backups = BackupManager(
        config.data_dir,
        config.backup_dir,
        BackupPolicy(
            enabled=config.backup_enabled,
            interval_hours=config.backup_interval_hours,
            keep=config.backup_keep,
        ),
    )
    daemon = RuntimeDaemon(
        application,
        DaemonConfig(tick_interval_seconds=config.daemon_tick_seconds),
    )
    out.write(
        f"PAIOS daemon running (pid {os.getpid()},"
        f" tick every {config.daemon_tick_seconds:g}s, Ctrl+C stops)\n"
    )
    out.flush()

    iterations = 0

    def should_stop(_daemon) -> bool:
        nonlocal iterations
        iterations += 1
        try:
            backups.maybe_backup()
        except Exception:
            pass  # backup trouble must not kill the loop
        if max_iterations is not None and iterations >= max_iterations:
            return True
        return stop_marker.exists()

    try:
        # run_until is the blocking foreground loop: it begins, ticks,
        # evaluates the predicate after each tick, and finishes itself.
        daemon.run_until(should_stop)
    except KeyboardInterrupt:
        pass
    finally:
        if daemon.state.value not in ("Stopped", "Created"):
            try:
                daemon.stop()
            except Exception:
                pass
        if detach is not None:
            try:
                detach()
            except Exception:
                pass
        if application.started:
            application.stop()
        pid_path.unlink(missing_ok=True)
        stop_marker.unlink(missing_ok=True)
        out.write("PAIOS daemon stopped.\n")
        out.flush()
    return 0


# --- background ------------------------------------------------------------


def start_background(config: SystemConfig) -> str:
    pid = read_pid(config)
    if pid is not None and process_alive(pid):
        return f"Daemon already running (pid {pid})."
    Path(config.log_dir).mkdir(parents=True, exist_ok=True)
    stop_file(config).unlink(missing_ok=True)
    command = [sys.executable, "-m", "paios.cli", "daemon", "run"]
    if config.source:
        command += ["--config", config.source]
    log_path = Path(config.log_dir) / "paios-daemon.out"
    creation_flags = 0
    if os.name == "nt":
        creation_flags = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )
    with open(log_path, "ab") as sink:
        process = subprocess.Popen(
            command,
            stdout=sink,
            stderr=sink,
            stdin=subprocess.DEVNULL,
            creationflags=creation_flags,
        )
    pid_file(config).write_text(str(process.pid), encoding="utf-8")
    return f"Daemon started in the background (pid {process.pid})."


def stop_background(config: SystemConfig, timeout_seconds: float = 30) -> str:
    pid = read_pid(config)
    if pid is None or not process_alive(pid):
        pid_file(config).unlink(missing_ok=True)
        return "Daemon is not running."
    stop_file(config).parent.mkdir(parents=True, exist_ok=True)
    stop_file(config).write_text("stop", encoding="utf-8")
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not process_alive(pid):
            pid_file(config).unlink(missing_ok=True)
            stop_file(config).unlink(missing_ok=True)
            return f"Daemon stopped (pid {pid})."
        time.sleep(0.2)
    return (
        f"Daemon (pid {pid}) did not stop within {timeout_seconds:g}s —"
        " it will exit at its next tick; check again with"
        " `paios daemon status`."
    )


def restart_background(config: SystemConfig) -> str:
    first = stop_background(config)
    second = start_background(config)
    return f"{first}\n{second}"


def daemon_status(config: SystemConfig) -> str:
    pid = read_pid(config)
    if pid is None:
        return "not running (no pid file)"
    if process_alive(pid):
        return f"running (pid {pid})"
    return f"not running (stale pid file for pid {pid})"
