"""Clock abstraction — the Clock owns Time (RUNTIME_EXECUTION.md section 2).

Every runtime component consumes time exclusively through the Clock
interface. ``SystemClock.now`` is the SINGLE SANCTIONED call site of the
operating-system clock in the entire PAIOS codebase (approved resolution
C6); the architecture audit verifies no other occurrence exists. The
Domain Layer remains clock-free — it receives time as arguments.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta


class Clock(ABC):
    """Produces current System Time and synchronizes all components."""

    @abstractmethod
    def now(self) -> datetime:
        """The current moment every component reasons relative to."""


class SystemClock(Clock):
    """Reads the operating-system clock — nowhere else may do so."""

    def now(self) -> datetime:
        return datetime.now()  # the single sanctioned call site (C6)


class ManualClock(Clock):
    """A deterministic clock for tests and controlled execution."""

    def __init__(self, initial: datetime) -> None:
        self._current = initial

    def now(self) -> datetime:
        return self._current

    def set_time(self, moment: datetime) -> None:
        self._current = moment

    def advance(self, delta: timedelta) -> None:
        self._current = self._current + delta
