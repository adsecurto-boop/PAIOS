"""Event Outcome value object.

Outcome answers "What actually happened?" — an immutable result recorded
alongside the Event lifecycle, not a competing lifecycle state
(STATE_MACHINES.md section 1, "Event outcome"; approved Resolution 5).
Lifecycle and Outcome are independent concepts.
"""

from dataclasses import dataclass
from datetime import datetime

from paios.domain.enums import EventOutcomeType


@dataclass(frozen=True, slots=True)
class EventOutcome:
    """Immutable execution evidence for one Event."""

    outcome_type: EventOutcomeType
    recorded_at: datetime
    note: str | None = None
