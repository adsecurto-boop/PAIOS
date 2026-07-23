"""The Decision Engine: the pure reasoning pipeline (DECISION_ENGINE.md §3).

    RuntimeSnapshot -> validate -> generate candidates -> filter (recorded
    rejections) -> rank -> confidence -> build Recommendations +
    Explanations -> DecisionResult (or a valid No-Action signal)

Pure function of its input: no state between invocations, no side
effects, no clock, no I/O, no mutation of anything in the snapshot.
Given identical snapshots the result — including Recommendation IDs — is
identical. Publishing/persisting the result is composition-layer work
(deferred by design); the Scheduler consumes accepted Recommendations
later.
"""

from dataclasses import dataclass

from paios.domain.entities.recommendation import Recommendation
from paios.decision_engine.confidence import Confidence, compute_confidence
from paios.decision_engine.evaluator import (
    CandidateFilter,
    RejectedCandidate,
    validate_snapshot,
)
from paios.decision_engine.explanation import Explanation, build_explanation
from paios.decision_engine.recommendation_builder import build_recommendation
from paios.decision_engine.rules import Candidate, Rule, default_rules
from paios.decision_engine.scoring import Score, rank_candidates
from paios.runtime.runtime_snapshot import RuntimeSnapshot

#: Domain-Policy cap (evolvable): guidance, not a flood of suggestions.
MAX_RECOMMENDATIONS = 5


@dataclass(frozen=True)
class ReasonedRecommendation:
    """One Recommendation with its full reasoning trail — never black-box."""

    recommendation: Recommendation
    explanation: Explanation
    score: Score
    confidence: Confidence


@dataclass(frozen=True)
class DecisionResult:
    """The engine's complete, explainable output for one snapshot."""

    generated_at: object  # datetime — the snapshot's Current Time
    recommendations: tuple[ReasonedRecommendation, ...]
    rejected: tuple[RejectedCandidate, ...]
    no_action: bool
    no_action_reason: str | None = None

    @property
    def priority_evaluation(self) -> tuple[tuple[str, float], ...]:
        """Ordered (reason, priority) pairs — the §8 Priority Evaluation."""
        return tuple(
            (
                reasoned.recommendation.reason,
                reasoned.score.total,
            )
            for reasoned in self.recommendations
        )


class DecisionEngine:
    """Stateless reasoning: holds only its immutable rule set — no data,
    no caches, no memory between invocations."""

    def __init__(self, rules: tuple[Rule, ...] | None = None) -> None:
        self._rules: tuple[Rule, ...] = rules if rules is not None else default_rules()
        self._filter = CandidateFilter()

    @property
    def rules(self) -> tuple[Rule, ...]:
        return self._rules

    def evaluate(self, snapshot: RuntimeSnapshot) -> DecisionResult:
        """Reason over one snapshot; pure and deterministic."""
        validate_snapshot(snapshot)

        candidates: list[Candidate] = []
        for rule in self._rules:
            candidates.extend(rule.evaluate(snapshot))

        accepted, rejected = self._filter.apply(snapshot, tuple(candidates))
        ranked = rank_candidates(snapshot, accepted)[:MAX_RECOMMENDATIONS]

        reasoned: list[ReasonedRecommendation] = []
        for candidate, score in ranked:
            confidence = compute_confidence(snapshot, candidate)
            recommendation = build_recommendation(
                snapshot, candidate, score, confidence
            )
            reasoned.append(
                ReasonedRecommendation(
                    recommendation=recommendation,
                    explanation=build_explanation(candidate, score, confidence),
                    score=score,
                    confidence=confidence,
                )
            )

        if not reasoned:
            return DecisionResult(
                generated_at=snapshot.current_time,
                recommendations=(),
                rejected=rejected,
                no_action=True,
                no_action_reason=(
                    "No candidate action is appropriate for the current "
                    "state; continuing as-is is the best decision "
                    "(a valid Decision Engine outcome per "
                    "DECISION_ENGINE.md section 8)"
                ),
            )
        return DecisionResult(
            generated_at=snapshot.current_time,
            recommendations=tuple(reasoned),
            rejected=rejected,
            no_action=False,
        )
