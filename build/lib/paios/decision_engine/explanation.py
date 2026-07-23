"""Explanations (DECISION_ENGINE.md §8): no black-box recommendations.

The Explanation is a first-class Decision Engine output, owned by the
engine, paired with each Recommendation: why it was made, which facts
were used, which Principles influenced it, its confidence, and the
expected impact.
"""

from dataclasses import dataclass

from paios.decision_engine.confidence import Confidence
from paios.decision_engine.rules import Candidate
from paios.decision_engine.scoring import Score


@dataclass(frozen=True)
class Explanation:
    why: str
    facts_used: tuple[str, ...]
    principles_influenced: tuple[str, ...]
    confidence_level: str
    confidence_value: float
    expected_impact: str
    score_components: tuple[tuple[str, float], ...]


def build_explanation(
    candidate: Candidate, score: Score, confidence: Confidence
) -> Explanation:
    return Explanation(
        why=candidate.reason,
        facts_used=candidate.facts,
        principles_influenced=candidate.aligned_principles,
        confidence_level=confidence.level.value,
        confidence_value=confidence.value,
        expected_impact=candidate.expected_benefit,
        score_components=tuple(sorted(score.components.items())),
    )
