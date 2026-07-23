"""The Planner interface — plan computation behind an abstraction
(refinement 3).

The Scheduler orchestrates; the Planner computes plans. A future AI
planner replaces DeterministicPlanner without any Scheduler change. The
Planner receives immutable candidates and returns an immutable plan; it
performs no reasoning about desirability — priority values are supplied
data (Decision Engine output), never computed here.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta

from paios.domain.value_objects.identifiers import EventId, RecommendationId
from paios.scheduler.plan import PlanEntry, SchedulingPlan

#: Slot length used when no duration evidence exists. A Domain Policy
#: (evolvable), not architecture: no domain field carries a planned
#: duration for a Recommendation, so sequencing needs a working default.
DEFAULT_SLOT_MINUTES = 60


@dataclass(frozen=True, slots=True)
class PlanCandidate:
    """Immutable planning input: typed IDs and supplied planning facts."""

    event_id: EventId
    priority: float
    earliest_start: datetime
    duration_minutes: int = DEFAULT_SLOT_MINUTES
    recommendation_id: RecommendationId | None = None


class Planner(ABC):
    """Computes a SchedulingPlan from immutable candidates."""

    @abstractmethod
    def plan(
        self, current_time: datetime, candidates: tuple[PlanCandidate, ...]
    ) -> SchedulingPlan:
        """Return a valid future-only, overlap-free plan."""


class DeterministicPlanner(Planner):
    """The Milestone 4 planner: fully deterministic slotting.

    Ordering: priority descending, then earliest start ascending, then
    Event ID (stable tiebreak). Slots are assigned sequentially from
    Current Time forward, never overlapping, never in the past.
    """

    def plan(
        self, current_time: datetime, candidates: tuple[PlanCandidate, ...]
    ) -> SchedulingPlan:
        ordered = sorted(
            candidates,
            key=lambda candidate: (
                -candidate.priority,
                candidate.earliest_start,
                str(candidate.event_id),
            ),
        )
        entries: list[PlanEntry] = []
        cursor = current_time
        for candidate in ordered:
            start = max(cursor, candidate.earliest_start, current_time)
            entries.append(
                PlanEntry(
                    event_id=candidate.event_id,
                    planned_start=start,
                    duration_minutes=candidate.duration_minutes,
                    priority=candidate.priority,
                    recommendation_id=candidate.recommendation_id,
                )
            )
            cursor = start + timedelta(minutes=candidate.duration_minutes)
        return SchedulingPlan(created_at=current_time, entries=tuple(entries))
