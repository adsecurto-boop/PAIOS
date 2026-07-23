"""The Runtime Daemon — the Timer Engine driving Application.tick().

    loop -> clock.now() -> Application.tick() -> sleep -> repeat

The daemon knows nothing about what a tick does. Scheduling is drift-free
via absolute deadlines: each deadline is the previous one plus the
interval; the daemon sleeps only the remaining gap and never accumulates
tick-duration error. If it falls behind, it catches up without sleeping.

The clock is obtained through the Application's components surface and
duck-typed (`now` / `advance` / `set_time`) — the daemon imports only
paios.application and stdlib.
"""

import threading
from datetime import datetime, timedelta
from typing import Callable

from paios.application.application import Application
from paios.daemon.config import SIGNAL_POLL_SECONDS, DaemonConfig
from paios.daemon.exceptions import ClockAdvanceError, DaemonStateError
from paios.daemon.lifecycle import DaemonState, validate_transition
from paios.daemon.sleep import RealSleep, SleepStrategy


class RuntimeDaemon:
    """Owns the eternal loop; owns nothing else."""

    def __init__(
        self, application: Application, config: DaemonConfig | None = None
    ) -> None:
        self._app = application
        self._config = config if config is not None else DaemonConfig()
        self._sleep: SleepStrategy = (
            self._config.sleep_strategy
            if self._config.sleep_strategy is not None
            else RealSleep()
        )
        self._state = DaemonState.CREATED
        self._stop_event = threading.Event()
        self._resume_event = threading.Event()
        self._resume_event.set()  # not paused
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self.tick_count = 0
        self.last_tick_at: datetime | None = None
        self.last_result = None
        self.last_error: Exception | None = None

    # --- introspection ---------------------------------------------------

    @property
    def state(self) -> DaemonState:
        return self._state

    @property
    def config(self) -> DaemonConfig:
        return self._config

    # --- clock access (duck-typed via the Application) --------------------

    def _clock(self):
        self._ensure_app_started()
        return self._app.components.clock

    def _ensure_app_started(self) -> None:
        if not self._app.started:
            self._app.start()

    def advance(self, minutes: float = 0, seconds: float = 0) -> None:
        """Advance a ManualClock deterministically (testing support)."""
        clock = self._clock()
        if not hasattr(clock, "advance"):
            raise ClockAdvanceError(
                "The active clock cannot be advanced (SystemClock)"
            )
        clock.advance(timedelta(minutes=minutes, seconds=seconds))

    def advance_to(self, moment: datetime) -> None:
        clock = self._clock()
        if not hasattr(clock, "set_time"):
            raise ClockAdvanceError(
                "The active clock cannot be advanced (SystemClock)"
            )
        if moment < clock.now():
            raise ClockAdvanceError(
                "Time advances monotonically; cannot move backwards"
            )
        clock.set_time(moment)

    # --- lifecycle --------------------------------------------------------

    def _transition(self, target: DaemonState) -> None:
        with self._lock:
            validate_transition(self._state, target)
            self._state = target

    def start(self) -> None:
        """Run the eternal loop on a background thread."""
        self._begin()
        self._thread = threading.Thread(
            target=self._loop_and_finish, name="paios-daemon", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Graceful shutdown: signal, then wait up to the timeout."""
        if self._state in (DaemonState.CREATED, DaemonState.STOPPED):
            raise DaemonStateError(
                f"Nothing to stop; daemon is {self._state.value!r}"
            )
        self._stop_event.set()
        self._resume_event.set()  # a paused loop must observe the stop
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=self._config.shutdown_timeout_seconds)
            self._thread = None

    def pause(self) -> None:
        self._transition(DaemonState.PAUSED)
        self._resume_event.clear()

    def resume(self) -> None:
        if self._state is not DaemonState.PAUSED:
            raise DaemonStateError(
                f"Cannot resume from {self._state.value!r}; only Paused"
            )
        self._transition(DaemonState.RUNNING)
        self._resume_event.set()

    # --- ticking ----------------------------------------------------------

    def tick_once(self):
        """One tick, exactly the loop body — usable in any non-paused,
        non-stopping state without changing lifecycle state."""
        if self._state in (DaemonState.PAUSED, DaemonState.STOPPING):
            raise DaemonStateError(
                f"Cannot tick while {self._state.value!r}"
            )
        return self._tick()

    def _tick(self):
        self._ensure_app_started()
        result = self._app.tick()
        self.tick_count += 1
        self.last_tick_at = self._app.components.clock.now()
        self.last_result = result
        return result

    def run_forever(self) -> None:
        """Blocking eternal loop; ends only via stop() or a tick error."""
        self._begin()
        self._loop_and_finish()
        if self.last_error is not None:
            raise self.last_error

    def run_until(self, predicate: Callable[["RuntimeDaemon"], bool]) -> None:
        """Loop until predicate(daemon) is true after a tick."""
        self._begin()
        self._loop_and_finish(predicate=predicate)
        if self.last_error is not None:
            raise self.last_error

    def run_iterations(self, iterations: int) -> None:
        """Exactly `iterations` ticks (or fewer if stopped), then finish."""
        self._begin()
        self._loop_and_finish(max_iterations=iterations)
        if self.last_error is not None:
            raise self.last_error

    # --- the loop ---------------------------------------------------------

    def _begin(self) -> None:
        self._transition(DaemonState.RUNNING)
        self._stop_event.clear()
        self._resume_event.set()
        self.last_error = None
        self._ensure_app_started()

    def _finish(self) -> None:
        with self._lock:
            if self._state in (DaemonState.RUNNING, DaemonState.PAUSED):
                validate_transition(self._state, DaemonState.STOPPING)
                self._state = DaemonState.STOPPING
            if self._state is DaemonState.STOPPING:
                self._state = DaemonState.STOPPED

    def _loop_and_finish(self, max_iterations=None, predicate=None) -> None:
        try:
            self._loop(max_iterations=max_iterations, predicate=predicate)
        except Exception as error:  # captured; foreground callers re-raise
            self.last_error = error
        finally:
            self._finish()

    def _loop(self, max_iterations=None, predicate=None) -> None:
        clock = self._clock()
        interval = timedelta(seconds=self._config.tick_interval_seconds)
        if self._config.startup_delay_seconds > 0:
            self._sleep.sleep(self._config.startup_delay_seconds)
        deadline: datetime | None = None
        iterations = 0
        while not self._stop_event.is_set():
            if not self._resume_event.is_set():  # paused
                self._resume_event.wait(SIGNAL_POLL_SECONDS)
                continue
            tick_start = clock.now()
            self._tick()
            iterations += 1
            if max_iterations is not None and iterations >= max_iterations:
                break
            if predicate is not None and predicate(self):
                break
            # Drift-free: absolute deadlines, never cumulative sleeps.
            deadline = (
                tick_start + interval if deadline is None else deadline + interval
            )
            remaining = (deadline - clock.now()).total_seconds()
            if remaining > 0:
                self._sleep.sleep(remaining)
            else:
                deadline = clock.now()  # behind schedule: catch up, no spiral
