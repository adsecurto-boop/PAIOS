"""The Notification value: what the manager produces and providers send."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, unique
from itertools import count

_sequence = count(1)


@unique
class Severity(Enum):
    INFO = "Info"          # ambient (time progress, context switches)
    NORMAL = "Normal"      # the default for user-relevant happenings
    CRITICAL = "Critical"  # bypasses quiet hours (high-severity disturbance)


@unique
class Category(Enum):
    RECOMMENDATION = "Recommendation"
    EVENT = "Event"
    CONTEXT = "Context"
    DISTURBANCE = "Disturbance"
    TIME = "Time"
    LEARNING = "Learning"
    SYSTEM = "System"


@dataclass
class Notification:
    category: Category
    title: str
    message: str
    severity: Severity
    occurred_at: datetime
    #: Set by the history when the user views/acknowledges it.
    read: bool = False
    #: Monotonic per-process id (display/order only, not persistence).
    notification_id: int = field(default_factory=lambda: next(_sequence))

    @property
    def dedup_key(self) -> str:
        """Identical content -> identical key (the cooldown identity)."""
        return f"{self.category.value}:{self.message}"
