"""MetadataPlanner: the R3 Planner seam put to work.

Implements the existing ``Planner`` interface (scheduler/planner.py) and
is injected through the existing ``Scheduler(kernel, planner=...)``
constructor parameter at composition time — the Scheduler core is
untouched (Milestone 20 approved proposal, section 5.2).

What it adds over DeterministicPlanner, all from sidecar metadata:

    - per-event estimated durations (falling back to the 60-minute
      Domain Policy default),
    - deadline pressure as an ordering refinement inside equal
      priority (priority stays supplied data — never computed here),
    - dependency ordering: a candidate whose prerequisite is also
      plannable is slotted after that prerequisite. A prerequisite
      that is absent (completed, cancelled, archived) constrains
      nothing.

The output contract is DeterministicPlanner's exactly: future-only,
overlap-free, deterministic for identical inputs.
"""

from datetime import datetime, timedelta

from paios.scheduler.plan import PlanEntry, SchedulingPlan
from paios.scheduler.planner import (
    DEFAULT_SLOT_MINUTES,
    PlanCandidate,
    Planner,
)
from paios.planning.stores import EventMetadataStore

#: Deadline used for ordering when a candidate has none: sorts last.
_NO_DEADLINE = datetime.max


class MetadataPlanner(Planner):
    def __init__(self, metadata: EventMetadataStore) -> None:
        self._metadata = metadata

    def plan(
        self, current_time: datetime, candidates: tuple[PlanCandidate, ...]
    ) -> SchedulingPlan:
        sidecars = {
            candidate.event_id: self._metadata.resolve(
                str(candidate.event_id),
                (
                    str(candidate.recommendation_id)
                    if candidate.recommendation_id is not None
                    else None
                ),
            )
            or {}
            for candidate in candidates
        }

        ordered = sorted(
            candidates,
            key=lambda candidate: (
                -candidate.priority,
                self._deadline_of(sidecars[candidate.event_id]),
                candidate.earliest_start,
                str(candidate.event_id),
            ),
        )
        ordered = self._respect_dependencies(ordered, sidecars)

        entries: list[PlanEntry] = []
        cursor = current_time
        for candidate in ordered:
            duration = self._duration_of(
                sidecars[candidate.event_id], candidate.duration_minutes
            )
            start = max(cursor, candidate.earliest_start, current_time)
            entries.append(
                PlanEntry(
                    event_id=candidate.event_id,
                    planned_start=start,
                    duration_minutes=duration,
                    priority=candidate.priority,
                    recommendation_id=candidate.recommendation_id,
                )
            )
            cursor = start + timedelta(minutes=duration)
        return SchedulingPlan(created_at=current_time, entries=tuple(entries))

    # --- metadata readers (tolerant: malformed sidecars constrain nothing)

    @staticmethod
    def _deadline_of(sidecar: dict) -> datetime:
        raw = sidecar.get("deadline")
        if not raw:
            return _NO_DEADLINE
        try:
            return datetime.fromisoformat(str(raw))
        except ValueError:
            return _NO_DEADLINE

    @staticmethod
    def _duration_of(sidecar: dict, supplied: int) -> int:
        estimated = sidecar.get("estimated_duration_minutes")
        if isinstance(estimated, int) and not isinstance(estimated, bool):
            if 1 <= estimated <= 24 * 60:
                return estimated
        return supplied if supplied else DEFAULT_SLOT_MINUTES

    def _respect_dependencies(
        self,
        ordered: list[PlanCandidate],
        sidecars: dict,
    ) -> list[PlanCandidate]:
        """Move dependents after their plannable prerequisites. Bounded
        passes keep cycles harmless (a cycle simply stops moving)."""
        plannable_keys = {
            str(candidate.event_id): candidate for candidate in ordered
        }
        for candidate in ordered:
            recommendation_id = candidate.recommendation_id
            if recommendation_id is not None:
                plannable_keys.setdefault(str(recommendation_id), candidate)

        result = list(ordered)
        for _ in range(len(result)):
            moved = False
            for index, candidate in enumerate(result):
                prerequisites = sidecars[candidate.event_id].get(
                    "depends_on", []
                )
                if not isinstance(prerequisites, list):
                    continue
                latest = -1
                for key in prerequisites:
                    prerequisite = plannable_keys.get(str(key))
                    if prerequisite is None or prerequisite is candidate:
                        continue
                    position = next(
                        (
                            other_index
                            for other_index, other in enumerate(result)
                            if other.event_id == prerequisite.event_id
                        ),
                        -1,
                    )
                    latest = max(latest, position)
                if latest > index:
                    result.pop(index)
                    result.insert(latest, candidate)
                    moved = True
                    break
            if not moved:
                break
        return result
