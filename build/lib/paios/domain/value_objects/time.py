"""Time value objects.

Time is the heartbeat of PAIOS (DOMAIN_MODEL.md Principle 16): everything
reasons relative to Current Time. The domain layer models durations and time
ranges as value objects; Current Time itself is supplied by callers (later,
the Clock / Runtime Kernel) — the domain never reads the system clock.

Durations are measured in minutes (ENTITY_RELATIONSHIPS.md schema:
"Duration: number (minutes)").
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from paios.domain.errors import DomainValidationError


@dataclass(frozen=True, slots=True)
class Duration:
    """A non-negative length of time, in minutes."""

    minutes: int

    def __post_init__(self) -> None:
        if not isinstance(self.minutes, int) or isinstance(self.minutes, bool):
            raise DomainValidationError("Duration.minutes must be an integer")
        if self.minutes < 0:
            raise DomainValidationError("Duration cannot be negative")

    @classmethod
    def from_timedelta(cls, delta: timedelta) -> "Duration":
        return cls(int(delta.total_seconds() // 60))

    @classmethod
    def between(cls, start: datetime, end: datetime) -> "Duration":
        if end < start:
            raise DomainValidationError("Duration.between requires end >= start")
        return cls.from_timedelta(end - start)

    def to_timedelta(self) -> timedelta:
        return timedelta(minutes=self.minutes)


@dataclass(frozen=True, slots=True)
class TimeRange:
    """A bounded interval: start time and end time, end never before start."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise DomainValidationError("TimeRange end cannot precede start")

    @property
    def duration(self) -> Duration:
        return Duration.between(self.start, self.end)

    def contains(self, moment: datetime) -> bool:
        return self.start <= moment <= self.end
