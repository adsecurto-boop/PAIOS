"""Child-process supervision: the heart of PAIOS.exe.

The launcher owns three children — daemon, REST API, desktop GUI —
each a `paios` / `paios_gui` command-line process (the M16 public
surfaces; no frozen code is imported here, let alone changed). The
supervisor starts them in order, polls them, restarts crashed ones
with bounded backoff, writes a crash report for every unexpected
death, and shuts everything down in reverse order.

Semantics:

- An exit the supervisor requested (stop/pause/shutdown) is *expected*.
- An unexpected exit with code 0 is a *clean exit* (the user closed the
  GUI window, or stopped the daemon via `paios daemon stop`): the child
  is left stopped — restarting it would fight the user.
- An unexpected non-zero exit is a *crash*: a crash log is written and
  the child is restarted with backoff until the restart budget for the
  policy window is exhausted, after which it is marked failed.

Graceful stop: an optional per-child pre-stop hook runs first (the
daemon's hook writes the M16 stop sentinel so the loop ends between
ticks), then the process is waited on briefly, then terminated, then
killed. The daemon checks its sentinel only between ticks (default
60 s apart), so a bounded wait with a terminate fallback is the honest
strategy — the store is written through on every mutation, so
terminate cannot lose committed data.
"""

import subprocess
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable


class ChildState(Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    CRASHED = "crashed"  # transient: crashed, restart pending
    FAILED = "failed"  # restart budget exhausted; needs manual restart


@dataclass(frozen=True)
class RestartPolicy:
    max_restarts: int = 5
    window_seconds: float = 300.0
    backoff_seconds: tuple = (1.0, 2.0, 5.0, 10.0, 30.0)

    def backoff_for(self, attempt: int) -> float:
        """Delay before restart ``attempt`` (0-based), clamped to the
        last configured step."""
        if not self.backoff_seconds:
            return 0.0
        index = min(attempt, len(self.backoff_seconds) - 1)
        return self.backoff_seconds[index]


@dataclass(frozen=True)
class ChildSpec:
    name: str
    command: tuple
    restart_on_crash: bool = True
    policy: RestartPolicy = field(default_factory=RestartPolicy)
    stop_timeout_seconds: float = 8.0
    #: Runs before the process is waited on during a graceful stop
    #: (e.g. write the daemon's stop sentinel). Must not raise.
    pre_stop: Callable[[], None] | None = None
    #: Where the child's stdout+stderr are appended (None = discard).
    output_path: Path | None = None


@dataclass(frozen=True)
class SupervisorEvent:
    """One observable lifecycle fact, for logging and tests."""

    kind: str  # started | exited | crashed | restarted | failed | stopped
    child: str
    detail: str = ""


class ManagedChild:
    """One supervised process: spec + live handle + restart bookkeeping."""

    def __init__(self, spec: ChildSpec, *, now: Callable[[], float]) -> None:
        self.spec = spec
        self.state = ChildState.STOPPED
        self.process: subprocess.Popen | None = None
        self._now = now
        self._output_handle = None
        self._recent_restarts: deque[float] = deque()
        self._restart_due_at: float | None = None
        self._stop_requested = False

    # --- introspection -----------------------------------------------------

    @property
    def pid(self) -> int | None:
        return self.process.pid if self.process is not None else None

    @property
    def restart_count(self) -> int:
        return len(self._recent_restarts)

    def snapshot(self) -> dict:
        return {
            "state": self.state.value,
            "pid": self.pid if self.state == ChildState.RUNNING else None,
            "restarts": self.restart_count,
        }

    # --- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        if self.state == ChildState.RUNNING:
            return
        self._stop_requested = False
        self._restart_due_at = None
        sink = subprocess.DEVNULL
        if self.spec.output_path is not None:
            self.spec.output_path.parent.mkdir(parents=True, exist_ok=True)
            self._output_handle = open(self.spec.output_path, "ab")
            sink = self._output_handle
        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = (
                subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.CREATE_NO_WINDOW
            )
        try:
            self.process = subprocess.Popen(
                list(self.spec.command),
                stdout=sink,
                stderr=subprocess.STDOUT if sink is not subprocess.DEVNULL
                else subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=creation_flags,
            )
        except OSError:
            self._close_output()
            self.state = ChildState.FAILED
            raise
        self.state = ChildState.RUNNING

    def stop(self, *, paused: bool = False) -> None:
        """Graceful, bounded stop: pre-stop hook, wait, terminate, kill."""
        self._stop_requested = True
        self._restart_due_at = None
        target = ChildState.PAUSED if paused else ChildState.STOPPED
        process = self.process
        if process is None or process.poll() is not None:
            self._finish_exit(target)
            return
        if self.spec.pre_stop is not None:
            try:
                self.spec.pre_stop()
            except Exception:
                pass  # a stop hook must never block shutdown
        try:
            process.wait(timeout=self.spec.stop_timeout_seconds)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        self._finish_exit(target)

    def poll(self) -> SupervisorEvent | None:
        """Observe the process once; returns the resulting event, if any."""
        if self.state == ChildState.CRASHED:
            return self._maybe_restart()
        if self.state != ChildState.RUNNING or self.process is None:
            return None
        code = self.process.poll()
        if code is None:
            return None
        # The process is gone without us asking.
        self._close_output()
        if code == 0:
            self.state = ChildState.STOPPED
            return SupervisorEvent(
                "exited", self.spec.name, "clean exit (code 0); not restarted"
            )
        return self._register_crash(code)

    # --- crash / restart internals -----------------------------------------

    def _register_crash(self, code: int) -> SupervisorEvent:
        now = self._now()
        window_start = now - self.spec.policy.window_seconds
        while self._recent_restarts and self._recent_restarts[0] < window_start:
            self._recent_restarts.popleft()
        if (
            not self.spec.restart_on_crash
            or len(self._recent_restarts) >= self.spec.policy.max_restarts
        ):
            self.state = ChildState.FAILED
            return SupervisorEvent(
                "failed",
                self.spec.name,
                f"exit code {code}; restart budget exhausted"
                if self.spec.restart_on_crash
                else f"exit code {code}; restart disabled",
            )
        delay = self.spec.policy.backoff_for(len(self._recent_restarts))
        self._recent_restarts.append(now)
        self._restart_due_at = now + delay
        self.state = ChildState.CRASHED
        return SupervisorEvent(
            "crashed",
            self.spec.name,
            f"exit code {code}; restart in {delay:g}s"
            f" (attempt {len(self._recent_restarts)})",
        )

    def _maybe_restart(self) -> SupervisorEvent | None:
        if self._restart_due_at is None or self._now() < self._restart_due_at:
            return None
        try:
            self.start()
        except OSError as error:
            return SupervisorEvent(
                "failed", self.spec.name, f"restart failed: {error}"
            )
        return SupervisorEvent(
            "restarted", self.spec.name, f"pid {self.pid}"
        )

    def _finish_exit(self, target: ChildState) -> None:
        self._close_output()
        self.process = None
        self.state = target

    def _close_output(self) -> None:
        if self._output_handle is not None:
            try:
                self._output_handle.close()
            except OSError:
                pass
            self._output_handle = None


class Supervisor:
    """Ordered supervision of the product's children.

    ``on_event`` receives every SupervisorEvent (the launcher routes
    them to the structured log); ``crash_dir`` receives one report per
    unexpected non-zero exit.
    """

    def __init__(
        self,
        specs: list[ChildSpec],
        *,
        crash_dir: str | Path | None = None,
        on_event: Callable[[SupervisorEvent], None] | None = None,
        now: Callable[[], float] = time.monotonic,
        timestamp: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._children = {
            spec.name: ManagedChild(spec, now=now) for spec in specs
        }
        self._crash_dir = Path(crash_dir) if crash_dir else None
        self._on_event = on_event
        self._timestamp = timestamp

    # --- queries -----------------------------------------------------------

    def child(self, name: str) -> ManagedChild:
        return self._children[name]

    def status(self) -> dict:
        return {
            name: child.snapshot() for name, child in self._children.items()
        }

    def overall_state(self) -> str:
        """Aggregate for the tray icon: ok | paused | degraded | stopped."""
        states = {child.state for child in self._children.values()}
        if states <= {ChildState.STOPPED}:
            return "stopped"
        if ChildState.FAILED in states or ChildState.CRASHED in states:
            return "degraded"
        if ChildState.PAUSED in states:
            return "paused"
        return "ok"

    # --- lifecycle ---------------------------------------------------------

    def start_all(self) -> None:
        for child in self._children.values():
            child.start()
            self._emit(
                SupervisorEvent(
                    "started", child.spec.name, f"pid {child.pid}"
                )
            )

    def poll(self) -> list[SupervisorEvent]:
        events = []
        for child in self._children.values():
            event = child.poll()
            if event is None:
                continue
            if event.kind in ("crashed", "failed"):
                self._write_crash_report(child, event)
            self._emit(event)
            events.append(event)
        return events

    def shutdown(self) -> None:
        """Stop every child, reverse start order (GUI, API, daemon)."""
        for child in reversed(list(self._children.values())):
            was_running = child.state == ChildState.RUNNING
            child.stop()
            if was_running:
                self._emit(SupervisorEvent("stopped", child.spec.name))

    # --- runtime controls (tray) -------------------------------------------

    def pause(self, name: str) -> None:
        child = self._children[name]
        if child.state == ChildState.RUNNING:
            child.stop(paused=True)
        else:
            child.state = ChildState.PAUSED
        self._emit(SupervisorEvent("stopped", name, "paused"))

    def resume(self, name: str) -> None:
        child = self._children[name]
        if child.state != ChildState.RUNNING:
            child.start()
            self._emit(SupervisorEvent("started", name, f"pid {child.pid}"))

    def restart(self, name: str) -> None:
        child = self._children[name]
        if child.state == ChildState.RUNNING:
            child.stop()
        child.start()
        self._emit(
            SupervisorEvent("restarted", name, f"pid {child.pid} (manual)")
        )

    # --- internals ---------------------------------------------------------

    def _emit(self, event: SupervisorEvent) -> None:
        if self._on_event is not None:
            try:
                self._on_event(event)
            except Exception:
                pass  # observers never disturb supervision

    def _write_crash_report(
        self, child: ManagedChild, event: SupervisorEvent
    ) -> None:
        if self._crash_dir is None:
            return
        try:
            self._crash_dir.mkdir(parents=True, exist_ok=True)
            stamp = self._timestamp().strftime("%Y%m%d-%H%M%S")
            report = (
                self._crash_dir
                / f"paios-crash-{child.spec.name}-{stamp}.log"
            )
            lines = [
                f"child: {child.spec.name}",
                f"time: {self._timestamp().isoformat()}",
                f"command: {' '.join(str(p) for p in child.spec.command)}",
                f"outcome: {event.kind} — {event.detail}",
                "",
            ]
            tail = self._output_tail(child)
            if tail:
                lines.append("--- last output ---")
                lines.extend(tail)
            report.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError:
            pass  # crash reporting must never take the launcher down

    @staticmethod
    def _output_tail(child: ManagedChild, count: int = 50) -> list[str]:
        path = child.spec.output_path
        if path is None or not path.is_file():
            return []
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        return text.splitlines()[-count:]
