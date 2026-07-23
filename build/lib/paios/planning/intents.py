"""User intents: the additive bridge from "the user typed a plan" to the
frozen Recommendation -> Scheduler materialization pipeline.

An EventIntent is what the Planning Workspace, Inbox conversion,
Templates and Recurrences all reduce to. ``build_user_recommendation``
turns one intent into a Domain Recommendation:

    Generated (birth) -> present() -> Pending -> admit_recommendation
    -> user accept -> Scheduler consumes -> Event Scheduled (G1)

Identity is a uuid5 content hash (the codebase's determinism rule for
Recommendations) under a namespace distinct from the Decision Engine's,
so user intents can never collide with engine output.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from paios.domain.entities.recommendation import Recommendation
from paios.domain.value_objects.identifiers import (
    ProjectId,
    RecommendationId,
    UserId,
)

_ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "paios://planning/user-intent")

#: How long an un-consumed user intent stays valid. A planning-layer
#: default (evolvable), not a Domain rule.
DEFAULT_VALIDITY = timedelta(days=7)


@dataclass(frozen=True)
class EventIntent:
    """One user-authored future event, exactly as captured.

    ``salt`` disambiguates same-content intents born at the same
    moment (edit/duplicate compositions under a ManualClock, double
    submits): it is content-derived by the caller (e.g. the source
    event id), so identity stays deterministic.
    """

    user_id: UserId
    title: str
    suggested_time: datetime | None = None
    priority: float | None = None
    project_id: ProjectId | None = None
    expected_outcome: str | None = None
    salt: str | None = None


def intent_recommendation_id(
    intent: EventIntent, created_at: datetime
) -> RecommendationId:
    seed = "|".join(
        (
            str(intent.user_id),
            intent.title,
            intent.suggested_time.isoformat() if intent.suggested_time else "",
            created_at.isoformat(),
            intent.salt or "",
        )
    )
    return RecommendationId(str(uuid.uuid5(_ID_NAMESPACE, seed)))


def build_user_recommendation(
    intent: EventIntent, created_at: datetime
) -> Recommendation:
    """One intent -> one Generated Recommendation (nothing admitted or
    accepted here — the Application facade owns that composition)."""
    validity_anchor = max(
        created_at, intent.suggested_time or created_at
    )
    return Recommendation(
        recommendation_id=intent_recommendation_id(intent, created_at),
        user_id=intent.user_id,
        reason=intent.title,
        created_at=created_at,
        expires_at=validity_anchor + DEFAULT_VALIDITY,
        related_project_id=intent.project_id,
        priority=intent.priority,
        expected_benefit=intent.expected_outcome,
        suggested_timing=intent.suggested_time,
        confidence_score=None,
    )
