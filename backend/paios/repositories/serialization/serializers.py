"""Entity -> JSON-safe dict serializers.

Field names are snake_case, matching the storage examples in
ENTITY_RELATIONSHIPS.md. Lifecycle aggregates additionally persist their
full transition history (order preserved) and, for readability, their
current state — which is re-derived and verified on load.

Only public domain API is read: constructor fields and the ``transitions``
/ ``status`` / ``state`` / ``outcome`` properties.
"""

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
from paios.repositories.serialization.primitives import (
    serialize_datetime,
    serialize_duration,
    serialize_enum,
    serialize_id,
    serialize_outcome,
    serialize_resource_flow,
    serialize_transitions,
)


def serialize_user(user: User) -> dict:
    return {
        "user_id": serialize_id(user.user_id),
        "name": user.name,
        "created_at": serialize_datetime(user.created_at),
        "last_active": serialize_datetime(user.last_active),
    }


def serialize_principle(principle: Principle) -> dict:
    return {
        "principle_id": serialize_id(principle.principle_id),
        "name": principle.name,
        "description": principle.description,
        "category": serialize_enum(principle.category),
        "created_at": serialize_datetime(principle.created_at),
        "last_reviewed": serialize_datetime(principle.last_reviewed),
    }


def serialize_context(context: Context) -> dict:
    return {
        "context_id": serialize_id(context.context_id),
        "name": context.name,
        "created_at": serialize_datetime(context.created_at),
        "location": context.location,
        "people": list(context.people),
        "emotion": context.emotion,
        "trigger": context.trigger,
        "reason": context.reason,
        "environment": context.environment,
        "notes": context.notes,
    }


def serialize_context_window(window: ContextWindow) -> dict:
    return {
        "window_id": serialize_id(window.window_id),
        "context_id": serialize_id(window.context_id),
        "event_id": serialize_id(window.event_id),
        "start_time": serialize_datetime(window.start_time),
        "end_time": serialize_datetime(window.end_time),
        "duration": serialize_duration(window.duration),
        "reason_started": window.reason_started,
        "reason_ended": window.reason_ended,
        "current_state": serialize_enum(window.current_state),
        "transitions": serialize_transitions(window.transitions),
    }


def serialize_event(event: Event) -> dict:
    return {
        "event_id": serialize_id(event.event_id),
        "user_id": serialize_id(event.user_id),
        "project_id": serialize_id(event.project_id),
        "context_window_id": serialize_id(event.context_window_id),
        "category": event.category,
        "description": event.description,
        "start_time": serialize_datetime(event.start_time),
        "end_time": serialize_datetime(event.end_time),
        "duration": serialize_duration(event.duration),
        "impact_type": serialize_enum(event.impact_type),
        "priority_alignment_score": event.priority_alignment_score,
        "resource_flow": serialize_resource_flow(event.resource_flow),
        "expected_outcome": event.expected_outcome,
        "actual_outcome": event.actual_outcome,
        "reflection_id": serialize_id(event.reflection_id),
        "outcome": serialize_outcome(event.outcome),
        "status": serialize_enum(event.status),
        "transitions": serialize_transitions(event.transitions),
    }


def serialize_project(project: Project) -> dict:
    return {
        "project_id": serialize_id(project.project_id),
        "user_id": serialize_id(project.user_id),
        "name": project.name,
        "description": project.description,
        "status": serialize_enum(project.status),
        "created_at": serialize_datetime(project.created_at),
        "progress_id": serialize_id(project.progress_id),
    }


def serialize_progress(progress: Progress) -> dict:
    return {
        "progress_id": serialize_id(progress.progress_id),
        "project_id": serialize_id(progress.project_id),
        "completion_percentage": progress.completion_percentage,
        "knowledge_gained": progress.knowledge_gained,
        "habit_score": progress.habit_score,
        "resource_delta": progress.resource_delta,
        "velocity": progress.velocity,
        "estimated_completion": serialize_datetime(progress.estimated_completion),
        "confidence": progress.confidence,
        "last_updated": serialize_datetime(progress.last_updated),
    }


def serialize_resource(resource: Resource) -> dict:
    return {
        "resource_id": serialize_id(resource.resource_id),
        "user_id": serialize_id(resource.user_id),
        "type": serialize_enum(resource.type),
        "current_value": resource.current_value,
        "unit": resource.unit,
        "negative_allowed": resource.negative_allowed,
        "last_updated": serialize_datetime(resource.last_updated),
    }


def serialize_knowledge(knowledge: Knowledge) -> dict:
    return {
        "knowledge_id": serialize_id(knowledge.knowledge_id),
        "user_id": serialize_id(knowledge.user_id),
        "project_id": serialize_id(knowledge.project_id),
        "domain": knowledge.domain,
        "topic": knowledge.topic,
        "concept": knowledge.concept,
        "difficulty": knowledge.difficulty,
        "confidence": knowledge.confidence,
        "revision_count": knowledge.revision_count,
        "last_revision": serialize_datetime(knowledge.last_revision),
        "source": knowledge.source,
        "applied": knowledge.applied,
        "retention_score": knowledge.retention_score,
    }


def serialize_recommendation(recommendation: Recommendation) -> dict:
    return {
        "recommendation_id": serialize_id(recommendation.recommendation_id),
        "user_id": serialize_id(recommendation.user_id),
        "related_project_id": serialize_id(recommendation.related_project_id),
        "reason": recommendation.reason,
        "priority": recommendation.priority,
        "expected_benefit": recommendation.expected_benefit,
        "suggested_timing": serialize_datetime(recommendation.suggested_timing),
        "confidence_score": recommendation.confidence_score,
        "created_at": serialize_datetime(recommendation.created_at),
        "expires_at": serialize_datetime(recommendation.expires_at),
        "status": serialize_enum(recommendation.status),
        "transitions": serialize_transitions(recommendation.transitions),
    }


def serialize_event_disturber(disturber: EventDisturber) -> dict:
    return {
        "event_disturber_id": serialize_id(disturber.event_disturber_id),
        "user_id": serialize_id(disturber.user_id),
        "type": serialize_enum(disturber.type),
        "description": disturber.description,
        "severity": serialize_enum(disturber.severity),
        "occurred_at": serialize_datetime(disturber.occurred_at),
        "resulting_context_window_id": serialize_id(
            disturber.resulting_context_window_id
        ),
        "affected_scheduled_event_ids": [
            serialize_id(event_id)
            for event_id in disturber.affected_scheduled_event_ids
        ],
        "resolution_status": serialize_enum(disturber.resolution_status),
        "state": serialize_enum(disturber.state),
        "transitions": serialize_transitions(disturber.transitions),
    }


def serialize_reflection(reflection: Reflection) -> dict:
    return {
        "reflection_id": serialize_id(reflection.reflection_id),
        "event_id": serialize_id(reflection.event_id),
        "context_window_id": serialize_id(reflection.context_window_id),
        "facts": reflection.facts,
        "interpretation": reflection.interpretation,
        "root_cause": reflection.root_cause,
        "lesson_learned": reflection.lesson_learned,
        "improvement": reflection.improvement,
        "confidence": reflection.confidence,
        "created_at": serialize_datetime(reflection.created_at),
    }


def serialize_insight(insight: Insight) -> dict:
    return {
        "insight_id": serialize_id(insight.insight_id),
        "source_reflection_id": serialize_id(insight.source_reflection_id),
        "category": insight.category,
        "confidence": insight.confidence,
        "reusable": insight.reusable,
        "created_at": serialize_datetime(insight.created_at),
    }


def serialize_habit(habit: Habit) -> dict:
    return {
        "habit_id": serialize_id(habit.habit_id),
        "user_id": serialize_id(habit.user_id),
        "name": habit.name,
        "trigger": habit.trigger,
        "frequency": habit.frequency,
        "reward": habit.reward,
        "current_trend": habit.current_trend,
        "strength": habit.strength,
        "desired_state": habit.desired_state,
        "detected_at": serialize_datetime(habit.detected_at),
        "last_updated": serialize_datetime(habit.last_updated),
    }


def serialize_goal(goal: Goal) -> dict:
    return {
        "goal_id": serialize_id(goal.goal_id),
        "user_id": serialize_id(goal.user_id),
        "name": goal.name,
        "description": goal.description,
        "suggested_by": goal.suggested_by,
        "accepted_by_user": goal.accepted_by_user,
        "accepted_at": serialize_datetime(goal.accepted_at),
        "status": serialize_enum(goal.status),
        "related_project_ids": [
            serialize_id(project_id) for project_id in goal.related_project_ids
        ],
        "confidence_score": goal.confidence_score,
    }
