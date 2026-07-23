"""The Scheduling Plan — immutable, ID-only planning data (refinement 2).

Plan structures never hold Event or Recommendation objects: only typed
identifiers plus immutable planning facts. The plan is in-memory only and
is rebuilt from evidence at boot — there is no scheduler.json (ruling G3).
A recalculation replaces the plan wholesale with a new immutable value.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from paios.domain.value_objects.identifiers import EventId, RecommendationId
from paios.scheduler.exceptions import SchedulingConflictError


@dataclass(frozen=True, slots=True)
class PlanEntry:
    """One planned future slot: typed IDs and immutable planning facts."""

    event_id: EventId
    planned_start: datetime
    duration_minutes: int
    priority: float
    recommendation_id: RecommendationId | None = None

    @property
    def planned_end(self) -> datetime:
        return self.planned_start + timedelta(minutes=self.duration_minutes)


@dataclass(frozen=True, slots=True)
class SchedulingPlan:
    """An immutable, ordered set of future slots for one User."""

    created_at: datetime
    entries: tuple[PlanEntry, ...] = ()

    def __post_init__(self) -> None:
        ordered = sorted(self.entries, key=lambda entry: entry.planned_start)
        for earlier, later in zip(ordered, ordered[1:]):
            if later.planned_start < earlier.planned_end:
                raise SchedulingConflictError(
                    f"Plan entries overlap: {earlier.event_id} "
                    f"({earlier.planned_start} - {earlier.planned_end}) and "
                    f"{later.event_id} (starts {later.planned_start})"
                )
        object.__setattr__(self, "entries", tuple(ordered))

    @property
    def is_empty(self) -> bool:
        return not self.entries

    def entry_for(self, event_id: EventId) -> PlanEntry | None:
        for entry in self.entries:
            if entry.event_id == event_id:
                return entry
        return None

    def without(self, event_id: EventId) -> "SchedulingPlan":
        return SchedulingPlan(
            created_at=self.created_at,
            entries=tuple(
                entry for entry in self.entries if entry.event_id != event_id
            ),
        )

    def next_entry(self, after: datetime) -> PlanEntry | None:
        for entry in self.entries:
            if entry.planned_start >= after:
                return entry
        return None
