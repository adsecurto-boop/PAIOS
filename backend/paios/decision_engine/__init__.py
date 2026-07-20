"""PAIOS Decision Engine (Milestone 5).

The reasoning brain of PAIOS (DECISION_ENGINE.md): stateless, pure,
deterministic, explainable, side-effect free. It consumes ONLY a
RuntimeSnapshot and produces ONLY Recommendation entities (Generated
state) with Explanations, Scores, Confidence, and a valid No-Action
signal.

It never mutates domain entities, never calls repositories, never
schedules, never transitions Event states, never activates Context
Windows, never modifies Runtime State, and never reads the clock.
Deterministic expert-system reasoning — no AI, no ML, no randomness.
"""

from paios.decision_engine.confidence import (
    Confidence,
    ConfidenceLevel,
    compute_confidence,
)
from paios.decision_engine.engine import (
    DecisionEngine,
    DecisionResult,
    ReasonedRecommendation,
)
from paios.decision_engine.evaluator import (
    CandidateFilter,
    RejectedCandidate,
    validate_snapshot,
)
from paios.decision_engine.exceptions import (
    DecisionEngineError,
    InvalidSnapshotError,
)
from paios.decision_engine.explanation import Explanation, build_explanation
from paios.decision_engine.recommendation_builder import build_recommendation
from paios.decision_engine.rules import (
    Candidate,
    Rule,
    default_rules,
)
from paios.decision_engine.scoring import Score, rank_candidates, score_candidate

__all__ = [
    "Candidate",
    "CandidateFilter",
    "Confidence",
    "ConfidenceLevel",
    "DecisionEngine",
    "DecisionEngineError",
    "DecisionResult",
    "Explanation",
    "InvalidSnapshotError",
    "ReasonedRecommendation",
    "RejectedCandidate",
    "Rule",
    "Score",
    "build_explanation",
    "build_recommendation",
    "compute_confidence",
    "default_rules",
    "rank_candidates",
    "score_candidate",
    "validate_snapshot",
]
