"""Sleep strategies — how the daemon waits between ticks.

Every strategy records its calls, so tests can prove drift-free
scheduling. SimulatedSleep advances a ManualClock by exactly the
requested duration, making long-running loops fully deterministic.
"""

import time
from abc import ABC, abstractmethod
from datetime import timedelta


class SleepStrategy(ABC):
    """Waits for the requested number of seconds — nothing else."""

    def __init__(self) -> None:
        self.calls: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.calls.append(seconds)
        self._sleep(seconds)

    @abstractmethod
    def _sleep(self, seconds: float) -> None: ...


class RealSleep(SleepStrategy):
    """Wall-clock sleeping for SystemClock operation."""

    def _sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)


class NoSleep(SleepStrategy):
    """Never waits — for deterministic bounded runs (ManualClock)."""

    def _sleep(self, seconds: float) -> None:
        pass


class SimulatedSleep(SleepStrategy):
    """Advances a manual clock by exactly the requested duration —
    deterministic time flow for drift and long-run tests."""

    def __init__(self, clock) -> None:
        super().__init__()
        self._clock = clock

    def _sleep(self, seconds: float) -> None:
        if seconds > 0:
            self._clock.advance(timedelta(seconds=seconds))
