"""Recommendation construction — deterministic, snapshot-time-based.

Determinism constraints:
- IDs are uuid5 content hashes over (rule, key, snapshot time) — never
  uuid4, never random. Identical snapshots yield identical IDs.
- created_at is the snapshot's Current Time; expires_at follows the
  Domain-Policy validity window ("Recommendations expire" —
  BUSINESS_RULES.md). The engine never reads a clock.

The produced Recommendation is a NEW domain entity in its initial
Generated state — creating it is the engine's documented output, not a
mutation of anything (presentation to Pending is the Runtime's actor,
STATE_MACHINES.md §6).
"""

import uuid
from datetime import timedelta

from paios.domain.entities.recommendation import Recommendation
from paios.domain.value_objects.identifiers import RecommendationId
from paios.decision_engine.confidence import Confidence
from paios.decision_engine.rules import Candidate
from paios.decision_engine.scoring import Score
from paios.runtime.runtime_snapshot import RuntimeSnapshot

#: Domain-Policy validity window (evolvable): unaccepted suggestions lapse.
RECOMMENDATION_VALIDITY_MINUTES = 60

_ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "paios://decision-engine")


def deterministic_recommendation_id(
    snapshot: RuntimeSnapshot, candidate: Candidate
) -> RecommendationId:
    seed = "|".join(
        (
            candidate.rule_id,
            candidate.key,
            snapshot.current_time.isoformat(),
        )
    )
    return RecommendationId(str(uuid.uuid5(_ID_NAMESPACE, seed)))


def build_recommendation(
    snapshot: RuntimeSnapshot,
    candidate: Candidate,
    score: Score,
    confidence: Confidence,
) -> Recommendation:
    created_at = snapshot.current_time
    return Recommendation(
        recommendation_id=deterministic_recommendation_id(snapshot, candidate),
        user_id=candidate.user_id,
        reason=candidate.reason,
        created_at=created_at,
        expires_at=created_at + timedelta(minutes=RECOMMENDATION_VALIDITY_MINUTES),
        related_project_id=candidate.related_project_id,
        priority=score.total,
        expected_benefit=candidate.expected_benefit,
        suggested_timing=candidate.suggested_timing,
        confidence_score=confidence.value,
    )
