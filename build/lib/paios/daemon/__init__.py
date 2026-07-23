"""PAIOS Runtime Daemon / Timer Engine (Milestone 9).

Makes PAIOS operate continuously: the daemon drives Application.tick()
on a configurable cadence and owns NOTHING else — no business logic, no
domain knowledge, no scheduling, no reasoning, no runtime mutation.

    loop -> clock.now() -> Application.tick() -> sleep -> repeat

Dependencies: paios.application + stdlib. The clock is reached through
the Application's components surface and duck-typed — the daemon does not
import even the Clock module.
"""

from paios.daemon.config import DaemonConfig
from paios.daemon.daemon import RuntimeDaemon
from paios.daemon.exceptions import (
    ClockAdvanceError,
    DaemonError,
    DaemonStateError,
)
from paios.daemon.lifecycle import DaemonState
from paios.daemon.sleep import (
    NoSleep,
    RealSleep,
    SimulatedSleep,
    SleepStrategy,
)

__all__ = [
    "ClockAdvanceError",
    "DaemonConfig",
    "DaemonError",
    "DaemonState",
    "DaemonStateError",
    "NoSleep",
    "RealSleep",
    "RuntimeDaemon",
    "SimulatedSleep",
    "SleepStrategy",
]
