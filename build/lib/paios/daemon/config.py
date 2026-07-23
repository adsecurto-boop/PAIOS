"""Daemon configuration — every number named, nothing magic."""

from dataclasses import dataclass

from paios.daemon.exceptions import DaemonError
from paios.daemon.sleep import SleepStrategy

#: Default cadence: one tick per minute — the "balanced responsiveness and
#: efficiency" option from RUNTIME_EXECUTION.md section 3 (Tick Frequency).
DEFAULT_TICK_INTERVAL_SECONDS = 60.0
DEFAULT_STARTUP_DELAY_SECONDS = 0.0
DEFAULT_SHUTDOWN_TIMEOUT_SECONDS = 5.0
#: How often a paused or sleeping background loop re-checks its signals —
#: bounds stop() responsiveness.
SIGNAL_POLL_SECONDS = 0.05


@dataclass(frozen=True)
class DaemonConfig:
    tick_interval_seconds: float = DEFAULT_TICK_INTERVAL_SECONDS
    startup_delay_seconds: float = DEFAULT_STARTUP_DELAY_SECONDS
    shutdown_timeout_seconds: float = DEFAULT_SHUTDOWN_TIMEOUT_SECONDS
    #: None selects RealSleep at daemon construction time.
    sleep_strategy: SleepStrategy | None = None

    def __post_init__(self) -> None:
        if self.tick_interval_seconds <= 0:
            raise DaemonError("tick_interval_seconds must be positive")
        if self.startup_delay_seconds < 0:
            raise DaemonError("startup_delay_seconds cannot be negative")
        if self.shutdown_timeout_seconds < 0:
            raise DaemonError("shutdown_timeout_seconds cannot be negative")
