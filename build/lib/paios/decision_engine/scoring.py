"""Ranking (DECISION_ENGINE.md §6): fixed-weight, fully decomposed scores.

Every score is a sum of named components so ranking is explainable —
no black-box totals. Weights are Domain-Policy constants (evolvable,
documented); the dimensions map to §6: momentum preservation, goal
contribution, knowledge growth, habit formation, Principle alignment,
and historical success (Impact history of same-category Events).
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from paios.domain.enums import EventStatus, ImpactType
from paios.decision_engine.rules import Candidate
from paios.runtime.runtime_snapshot import RuntimeSnapshot

# --- Domain-Policy weights (evolvable, documented) ------------------------
WEIGHT_MOMENTUM = 1.5
WEIGHT_GOAL = 2.0
WEIGHT_KNOWLEDGE = 1.0
WEIGHT_HABIT = 1.0
WEIGHT_PER_PRINCIPLE = 0.5
MAX_PRINCIPLE_BONUS = 1.0
WEIGHT_HISTORY = 1.0


@dataclass(frozen=True)
class Score:
    """A decomposed, explainable score."""

    total: float
    components: Mapping[str, float]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "components", MappingProxyType(dict(self.components))
        )


def _historical_support(
    snapshot: RuntimeSnapshot, candidate: Candidate
) -> float:
    """+1 when same-category history skews Opportunity, -1 when it skews
    Distraction, 0 otherwise (§6 'Historical Success'; Impact history)."""
    opportunities = 0
    distractions = 0
    for event in snapshot.events:
        if (
            event.status is EventStatus.COMPLETED
            and event.category == candidate.category
        ):
            if event.impact_type is ImpactType.OPPORTUNITY:
                opportunities += 1
            elif event.impact_type is ImpactType.DISTRACTION:
                distractions += 1
    if opportunities > distractions:
        return WEIGHT_HISTORY
    if distractions > opportunities:
        return -WEIGHT_HISTORY
    return 0.0


def score_candidate(snapshot: RuntimeSnapshot, candidate: Candidate) -> Score:
    components: dict[str, float] = {"base_priority": candidate.base_priority}
    if candidate.momentum:
        components["momentum_preservation"] = WEIGHT_MOMENTUM
    if candidate.goal_aligned:
        components["goal_contribution"] = WEIGHT_GOAL
    if candidate.knowledge_growth:
        components["knowledge_growth"] = WEIGHT_KNOWLEDGE
    if candidate.habit_reinforcing:
        components["habit_formation"] = WEIGHT_HABIT
    if candidate.aligned_principles:
        components["principle_alignment"] = min(
            WEIGHT_PER_PRINCIPLE * len(candidate.aligned_principles),
            MAX_PRINCIPLE_BONUS,
        )
    history = _historical_support(snapshot, candidate)
    if history:
        components["historical_success"] = history
    return Score(total=sum(components.values()), components=components)


def rank_candidates(
    snapshot: RuntimeSnapshot, candidates: tuple[Candidate, ...]
) -> tuple[tuple[Candidate, Score], ...]:
    """Deterministic ranking: score descending, then rule ID and key as
    stable tiebreaks — identical inputs always produce identical order."""
    scored = [
        (candidate, score_candidate(snapshot, candidate))
        for candidate in candidates
    ]
    scored.sort(
        key=lambda pair: (-pair[1].total, pair[0].rule_id, pair[0].key)
    )
    return tuple(scored)
