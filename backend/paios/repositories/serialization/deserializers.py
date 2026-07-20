"""JSON dict -> entity deserializers.

Hydration is RECONSTITUTION, not replay: history is immutable evidence, so
loading restores evidence instead of re-executing lifecycle commands.
Lifecycle aggregates are rebuilt through the domain's reconstitution
factories (``Event.restore``, ``ContextWindow.restore``,
``Recommendation.restore``, ``EventDisturber.restore``), which:

- validate the transition chain STRUCTURALLY (legal state-machine edges,
  continuity, order preserved) via ``TransitionHistory.from_records``;
- apply evidence-shape rules (e.g. an Outcome requires a history through an
  outcome-permitting state) instead of re-running command preconditions —
  Policies adjudicate the future, never the past;
- return entities whose immutability guards are fully armed.

The stored current state is additionally verified against the
reconstituted state — an integrity check against hand-edited or truncated
files. Any record the domain rejects surfaces as SerializationError.
"""

from enum import Enum
from typing import Type

from paios.domain.entities.context import Context
from paios.domain.entities.context_window import ContextWindow
from paios.domain.entities.event import Event
from paios.domain.entities.event_disturber import EventDisturber
from paios.domain.entities.goal import Goal
from paios.domain.entities.habit import Habit
from paios.domain.entities.insight import Insight
from paios.domain.entities.knowledge import Knowledge
from paios.domain.entities.principle import Principle
from paios.domain.entities.progress import Progress
from paios.domain.entities.project import Project
from paios.domain.entities.recommendation import Recommendation
from paios.domain.entities.reflection import Reflection
from paios.domain.entities.resource import Resource
from paios.domain.entities.user import User
from paios.domain.enums import (
    ContextWindowState,
    DisturberResolutionStatus,
    DisturberSeverity,
    DisturberState,
    DisturberType,
    EventStatus,
    GoalStatus,
    ImpactType,
    PrincipleCategory,
    ProjectStatus,
    RecommendationStatus,
    ResourceType,
)
from paios.domain.value_objects.identifiers import (
    ContextId,
    ContextWindowId,
    EventDisturberId,
    EventId,
    GoalId,
    HabitId,
    InsightId,
    KnowledgeId,
    PrincipleId,
    ProgressId,
    ProjectId,
    RecommendationId,
    ReflectionId,
    ResourceId,
    UserId,
)
from paios.repositories.errors import SerializationError
from paios.repositories.serialization.primitives import (
    deserialization_guard,
    parse_datetime,
    parse_duration,
    parse_enum,
    parse_id,
    parse_outcome,
    parse_resource_flow,
    parse_transition_records,
)


def _verify_stored_state(
    kind: str, enum_cls: Type[Enum], stored_value: str | None, actual: Enum
) -> None:
    """The stored state is readability metadata, never the source of truth —
    it must agree with the state reconstituted from the evidence."""
    stored = parse_enum(enum_cls, stored_value)
    if stored is not None and stored is not actual:
        raise SerializationError(
            f"{kind}: stored state {stored.value!r} does not match "
            f"reconstituted state {actual.value!r}"
        )


# --- simple entities ------------------------------------------------------


def deserialize_user(data: dict) -> User:
    with deserialization_guard("User"):
        return User(
            user_id=parse_id(UserId, data["user_id"]),
            name=data["name"],
            created_at=parse_datetime(data["created_at"]),
            last_active=parse_datetime(data.get("last_active")),
        )


def deserialize_principle(data: dict) -> Principle:
    with deserialization_guard("Principle"):
        return Principle(
            principle_id=parse_id(PrincipleId, data["principle_id"]),
            name=data["name"],
            description=data["description"],
            category=parse_enum(PrincipleCategory, data["category"]),
            created_at=parse_datetime(data["created_at"]),
            last_reviewed=parse_datetime(data.get("last_reviewed")),
        )


def deserialize_context(data: dict) -> Context:
    with deserialization_guard("Context"):
        return Context(
            context_id=parse_id(ContextId, data["context_id"]),
            name=data["name"],
            created_at=parse_datetime(data["created_at"]),
            location=data.get("location"),
            people=tuple(data.get("people", [])),
            emotion=data.get("emotion"),
            trigger=data.get("trigger"),
            reason=data.get("reason"),
            environment=data.get("environment"),
            notes=data.get("notes"),
        )


def deserialize_project(data: dict) -> Project:
    with deserialization_guard("Project"):
        return Project(
            project_id=parse_id(ProjectId, data["project_id"]),
            user_id=parse_id(UserId, data["user_id"]),
            name=data["name"],
            description=data["description"],
            created_at=parse_datetime(data["created_at"]),
            progress_id=parse_id(ProgressId, data.get("progress_id")),
            status=parse_enum(ProjectStatus, data["status"]),
        )


def deserialize_progress(data: dict) -> Progress:
    with deserialization_guard("Progress"):
        return Progress(
            progress_id=parse_id(ProgressId, data["progress_id"]),
            project_id=parse_id(ProjectId, data["project_id"]),
            completion_percentage=data["completion_percentage"],
            knowledge_gained=data["knowledge_gained"],
            habit_score=data["habit_score"],
            resource_delta=data["resource_delta"],
            velocity=data["velocity"],
            estimated_completion=parse_datetime(data.get("estimated_completion")),
            confidence=data["confidence"],
            last_updated=parse_datetime(data.get("last_updated")),
        )


def deserialize_resource(data: dict) -> Resource:
    with deserialization_guard("Resource"):
        return Resource(
            resource_id=parse_id(ResourceId, data["resource_id"]),
            user_id=parse_id(UserId, data["user_id"]),
            type=parse_enum(ResourceType, data["type"]),
            current_value=data["current_value"],
            unit=data["unit"],
            negative_allowed=data.get("negative_allowed", False),
            last_updated=parse_datetime(data.get("last_updated")),
        )


def deserialize_knowledge(data: dict) -> Knowledge:
    with deserialization_guard("Knowledge"):
        return Knowledge(
            knowledge_id=parse_id(KnowledgeId, data["knowledge_id"]),
            user_id=parse_id(UserId, data["user_id"]),
            domain=data["domain"],
            topic=data["topic"],
            concept=data["concept"],
            project_id=parse_id(ProjectId, data.get("project_id")),
            difficulty=data.get("difficulty"),
            confidence=data["confidence"],
            revision_count=data["revision_count"],
            last_revision=parse_datetime(data.get("last_revision")),
            source=data.get("source"),
            applied=data["applied"],
            retention_score=data["retention_score"],
        )


def deserialize_reflection(data: dict) -> Reflection:
    with deserialization_guard("Reflection"):
        return Reflection(
            reflection_id=parse_id(ReflectionId, data["reflection_id"]),
            event_id=parse_id(EventId, data["event_id"]),
            context_window_id=parse_id(ContextWindowId, data["context_window_id"]),
            created_at=parse_datetime(data["created_at"]),
            facts=data.get("facts"),
            interpretation=data.get("interpretation"),
            root_cause=data.get("root_cause"),
            lesson_learned=data.get("lesson_learned"),
            improvement=data.get("improvement"),
            confidence=data.get("confidence"),
        )


def deserialize_insight(data: dict) -> Insight:
    with deserialization_guard("Insight"):
        return Insight(
            insight_id=parse_id(InsightId, data["insight_id"]),
            source_reflection_id=parse_id(
                ReflectionId, data["source_reflection_id"]
            ),
            created_at=parse_datetime(data["created_at"]),
            category=data.get("category"),
            confidence=data.get("confidence"),
            reusable=data["reusable"],
        )


def deserialize_habit(data: dict) -> Habit:
    """Rehydrate a previously inferred Habit.

    This is persistence rehydration, not creation: the Habit was originally
    inferred from Event history (the domain's sole creation path); loading
    it back is not a manual creation.
    """
    with deserialization_guard("Habit"):
        return Habit(
            habit_id=parse_id(HabitId, data["habit_id"]),
            user_id=parse_id(UserId, data["user_id"]),
            name=data["name"],
            detected_at=parse_datetime(data["detected_at"]),
            trigger=data.get("trigger"),
            frequency=data.get("frequency"),
            reward=data.get("reward"),
            current_trend=data.get("current_trend"),
            strength=data["strength"],
            desired_state=data.get("desired_state"),
            last_updated=parse_datetime(data.get("last_updated")),
        )


def deserialize_goal(data: dict) -> Goal:
    with deserialization_guard("Goal"):
        return Goal(
            goal_id=parse_id(GoalId, data["goal_id"]),
            user_id=parse_id(UserId, data["user_id"]),
            name=data["name"],
            description=data["description"],
            suggested_by=data["suggested_by"],
            accepted_by_user=data["accepted_by_user"],
            accepted_at=parse_datetime(data.get("accepted_at")),
            status=parse_enum(GoalStatus, data["status"]),
            related_project_ids=tuple(
                parse_id(ProjectId, project_id)
                for project_id in data.get("related_project_ids", [])
            ),
            confidence_score=data.get("confidence_score"),
        )


# --- lifecycle aggregates (reconstituted from evidence) -------------------


def deserialize_event(data: dict) -> Event:
    with deserialization_guard("Event"):
        event = Event.restore(
            event_id=parse_id(EventId, data["event_id"]),
            user_id=parse_id(UserId, data["user_id"]),
            context_window_id=parse_id(ContextWindowId, data["context_window_id"]),
            category=data["category"],
            description=data["description"],
            project_id=parse_id(ProjectId, data.get("project_id")),
            start_time=parse_datetime(data.get("start_time")),
            end_time=parse_datetime(data.get("end_time")),
            duration=parse_duration(data.get("duration")),
            impact_type=parse_enum(ImpactType, data.get("impact_type")),
            priority_alignment_score=data.get("priority_alignment_score"),
            resource_flow=parse_resource_flow(data.get("resource_flow")),
            expected_outcome=data.get("expected_outcome"),
            actual_outcome=data.get("actual_outcome"),
            reflection_id=parse_id(ReflectionId, data.get("reflection_id")),
            transitions=parse_transition_records(
                EventStatus, data.get("transitions", [])
            ),
            outcome=parse_outcome(data.get("outcome")),
        )
    _verify_stored_state("Event", EventStatus, data.get("status"), event.status)
    return event


def deserialize_context_window(data: dict) -> ContextWindow:
    with deserialization_guard("ContextWindow"):
        window = ContextWindow.restore(
            window_id=parse_id(ContextWindowId, data["window_id"]),
            context_id=parse_id(ContextId, data["context_id"]),
            event_id=parse_id(EventId, data["event_id"]),
            start_time=parse_datetime(data.get("start_time")),
            end_time=parse_datetime(data.get("end_time")),
            duration=parse_duration(data.get("duration")),
            reason_started=data.get("reason_started"),
            reason_ended=data.get("reason_ended"),
            transitions=parse_transition_records(
                ContextWindowState, data.get("transitions", [])
            ),
        )
    _verify_stored_state(
        "ContextWindow",
        ContextWindowState,
        data.get("current_state"),
        window.current_state,
    )
    return window


def deserialize_recommendation(data: dict) -> Recommendation:
    with deserialization_guard("Recommendation"):
        recommendation = Recommendation.restore(
            recommendation_id=parse_id(
                RecommendationId, data["recommendation_id"]
            ),
            user_id=parse_id(UserId, data["user_id"]),
            reason=data["reason"],
            created_at=parse_datetime(data["created_at"]),
            expires_at=parse_datetime(data["expires_at"]),
            related_project_id=parse_id(ProjectId, data.get("related_project_id")),
            priority=data.get("priority"),
            expected_benefit=data.get("expected_benefit"),
            suggested_timing=parse_datetime(data.get("suggested_timing")),
            confidence_score=data.get("confidence_score"),
            transitions=parse_transition_records(
                RecommendationStatus, data.get("transitions", [])
            ),
        )
    _verify_stored_state(
        "Recommendation",
        RecommendationStatus,
        data.get("status"),
        recommendation.status,
    )
    return recommendation


def deserialize_event_disturber(data: dict) -> EventDisturber:
    with deserialization_guard("EventDisturber"):
        disturber = EventDisturber.restore(
            event_disturber_id=parse_id(
                EventDisturberId, data["event_disturber_id"]
            ),
            user_id=parse_id(UserId, data["user_id"]),
            type=parse_enum(DisturberType, data["type"]),
            description=data["description"],
            severity=parse_enum(DisturberSeverity, data["severity"]),
            occurred_at=parse_datetime(data["occurred_at"]),
            resulting_context_window_id=parse_id(
                ContextWindowId, data.get("resulting_context_window_id")
            ),
            affected_scheduled_event_ids=tuple(
                parse_id(EventId, event_id)
                for event_id in data.get("affected_scheduled_event_ids", [])
            ),
            resolution_status=parse_enum(
                DisturberResolutionStatus, data["resolution_status"]
            ),
            transitions=parse_transition_records(
                DisturberState, data.get("transitions", [])
            ),
        )
    _verify_stored_state(
        "EventDisturber", DisturberState, data.get("state"), disturber.state
    )
    return disturber
