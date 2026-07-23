"""Snapshot validation and candidate filtering (DECISION_ENGINE.md §3, §5).

Validation is the documented lightweight, reasoning-specific check —
comprehensive system-wide validation is the Runtime Kernel's job.

Filters run in the documented order (§5): Principle violations first
(non-negotiable), then Resource infeasibility, then redundancy. Context
compatibility and time-window/priority-conflict filters are documented
deferrals: no domain field models a per-candidate Context requirement,
and Scheduler State is excluded from snapshots by ruling G7 — plan
conflicts remain the Scheduler's own deferral mechanism.

Every rejection is recorded with its reason: filtering is part of the
explanation, not a silent disappearance.
"""

from dataclasses import dataclass

from paios.domain.enums import RecommendationStatus, ResourceType
from paios.decision_engine.exceptions import InvalidSnapshotError
from paios.decision_engine.rules import Candidate
from paios.runtime.runtime_snapshot import RuntimeSnapshot


def validate_snapshot(snapshot: RuntimeSnapshot) -> None:
    """Reasoning-specific invariant checks (§3 'Validate Runtime State')."""
    if not isinstance(snapshot, RuntimeSnapshot):
        raise InvalidSnapshotError(
            "The Decision Engine reasons over RuntimeSnapshot instances only"
        )
    running = [event for event in snapshot.events if event.is_running]
    if len(running) > 1:
        raise InvalidSnapshotError(
            f"Snapshot violates 'exactly one Running Event': "
            f"{len(running)} user Events are running"
        )
    if snapshot.execution_context is None:
        raise InvalidSnapshotError(
            "Snapshot lacks an Execution Context; exactly one must exist"
        )


@dataclass(frozen=True)
class RejectedCandidate:
    """A filtered candidate with the reason it was rejected (§5)."""

    rule_id: str
    action: str
    reason: str


class CandidateFilter:
    """Applies the §5 filters in documented order; pure and deterministic."""

    def apply(
        self, snapshot: RuntimeSnapshot, candidates: tuple[Candidate, ...]
    ) -> tuple[tuple[Candidate, ...], tuple[RejectedCandidate, ...]]:
        accepted: list[Candidate] = []
        rejected: list[RejectedCandidate] = []
        for candidate in candidates:
            rejection = self._first_rejection(snapshot, candidate)
            if rejection is None:
                accepted.append(candidate)
            else:
                rejected.append(
                    RejectedCandidate(
                        rule_id=candidate.rule_id,
                        action=candidate.action,
                        reason=rejection,
                    )
                )
        return tuple(accepted), tuple(rejected)

    def _first_rejection(
        self, snapshot: RuntimeSnapshot, candidate: Candidate
    ) -> str | None:
        # 1. Principle violations — eliminated first, non-negotiable (§5).
        if candidate.violates_principles:
            violated = ", ".join(candidate.violates_principles)
            return f"Violates Principle(s): {violated}"
        # 2. Resource infeasibility — hard constraint (§5).
        if candidate.required_energy > 0:
            energy = self._energy_available(snapshot)
            if energy is not None and energy < candidate.required_energy:
                return (
                    f"Insufficient Energy: requires "
                    f"{candidate.required_energy:g}, available {energy:g}"
                )
        # 3. Redundancy — an unexpired Pending Recommendation with the same
        #    reason already awaits the user (§2 'Pending Recommendations'
        #    provide continuity; §5 redundancy check).
        for recommendation in snapshot.recommendations:
            if (
                recommendation.status is RecommendationStatus.PENDING
                and not recommendation.is_expired(snapshot.current_time)
                and recommendation.reason == candidate.reason
            ):
                return (
                    f"Already recommended and pending: "
                    f"{recommendation.recommendation_id}"
                )
        return None

    @staticmethod
    def _energy_available(snapshot: RuntimeSnapshot) -> float | None:
        """Total tracked Energy, or None when Energy is not tracked (an
        untracked Resource cannot fail a feasibility check — it lowers
        confidence instead, see confidence.py)."""
        values = [
            resource.current_value
            for resource in snapshot.resources
            if resource.type is ResourceType.ENERGY
        ]
        if not values:
            return None
        return sum(values)
