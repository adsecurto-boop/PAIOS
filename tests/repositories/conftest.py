"""Builders producing fully-populated domain objects for persistence tests.

Each builder exercises the richest legal shape of its aggregate — full
transition histories, value objects, optional fields — so that round-trip
tests prove lossless serialization.
"""

from datetime import datetime, timedelta

import pytest

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
    DisturberSeverity,
    DisturberType,
    EventOutcomeType,
    EventStatus,
    ImpactType,
    PrincipleCategory,
    ResourceType,
)
from paios.domain.value_objects.event_outcome import EventOutcome
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
from paios.domain.value_objects.resource_flow import ResourceFlow
from paios.domain.value_objects.time import Duration
from paios.repositories.json_store import JsonStore

T0 = datetime(2026, 7, 20, 9, 0)


def at(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


@pytest.fixture
def store(tmp_path) -> JsonStore:
    return JsonStore(tmp_path / "data")


def build_completed_event(event_id: str = "evt_001") -> Event:
    """An Event through its richest legal path, with every optional field."""
    event = Event(
        event_id=EventId(event_id),
        user_id=UserId("user_001"),
        context_window_id=ContextWindowId(f"win_{event_id}"),
        category="study",
        description="Studied ISTQB Chapter 3 - Test Management",
        project_id=ProjectId("proj_001"),
        start_time=T0,
        end_time=at(120),
        duration=Duration(120),
        impact_type=ImpactType.OPPORTUNITY,
        priority_alignment_score=9,
        resource_flow=ResourceFlow(
            consumed={ResourceType.TIME: 120, ResourceType.ENERGY: 20},
            produced={ResourceType.KNOWLEDGE: 35, ResourceType.CAREER: 25},
        ),
        expected_outcome="Complete Chapter 3 understanding",
        actual_outcome="Completed Chapter 3, took notes",
    )
    event.transition_to(EventStatus.SCHEDULED, at(1), reason="accepted")
    event.transition_to(EventStatus.READY, at(2))
    event.transition_to(EventStatus.STARTED, at(3))
    event.transition_to(EventStatus.INTERRUPTED, at(30), reason="emergency call")
    event.transition_to(EventStatus.RESUMED, at(45))
    event.transition_to(EventStatus.STARTED, at(46))
    event.transition_to(EventStatus.COMPLETED, at(120))
    event.record_outcome(
        EventOutcome(EventOutcomeType.COMPLETED, at(121), note="as planned")
    )
    event.link_reflection(ReflectionId("ref_001"))
    return event


def build_expired_window(window_id: str = "win_001") -> ContextWindow:
    window = ContextWindow(
        window_id=ContextWindowId(window_id),
        context_id=ContextId("ctx_001"),
        event_id=EventId("evt_001"),
    )
    window.activate(T0, reason_started="Arrived at office")
    window.mark_changing(at(60), reason="Team Lead requested overtime")
    window.expire(at(65), reason_ended="Replacement window active")
    return window


def build_consumed_recommendation(
    recommendation_id: str = "rec_001",
) -> Recommendation:
    recommendation = Recommendation(
        recommendation_id=RecommendationId(recommendation_id),
        user_id=UserId("user_001"),
        reason="Advance ISTQB certification project",
        created_at=T0,
        expires_at=at(120),
        related_project_id=ProjectId("proj_001"),
        priority=8.5,
        expected_benefit="Chapter 3 mastery",
        suggested_timing=at(10),
        confidence_score=0.87,
    )
    recommendation.present(at(1))
    recommendation.accept(at(5), reason="user accepted")
    recommendation.consume(at(6), reason="scheduled")
    return recommendation


def build_archived_disturber(
    disturber_id: str = "dist_001",
) -> EventDisturber:
    disturber = EventDisturber(
        event_disturber_id=EventDisturberId(disturber_id),
        user_id=UserId("user_001"),
        type=DisturberType.WORK,
        description="Team Lead requested overtime for production issue",
        severity=DisturberSeverity.HIGH,
        occurred_at=T0,
        affected_scheduled_event_ids=(EventId("evt_003"), EventId("evt_004")),
    )
    disturber.record(at(1))
    disturber.analyze(at(2))
    disturber.apply(at(3), ContextWindowId("win_002"))
    disturber.resolve(at(10))
    disturber.archive(at(60))
    return disturber


def build_user() -> User:
    user = User(user_id=UserId("user_001"), name="Test User", created_at=T0)
    user.record_activity(at(30))
    return user


def build_principle() -> Principle:
    return Principle(
        principle_id=PrincipleId("prin_001"),
        name="Protect Health",
        description="Prioritize actions that maintain or improve health",
        category=PrincipleCategory.HEALTH,
        created_at=T0,
    ).reviewed(at(10))


def build_context() -> Context:
    return Context(
        context_id=ContextId("ctx_001"),
        name="Office",
        created_at=T0,
        location="Downtown office, 4th floor",
        people=("Team Lead", "colleagues"),
        emotion="focused",
        trigger="workday",
        reason="employment",
        environment="Open workspace",
        notes="Primary workday location",
    )


def build_project() -> Project:
    project = Project(
        project_id=ProjectId("proj_001"),
        user_id=UserId("user_001"),
        name="ISTQB Certification",
        description="Complete ISTQB Foundation Level certification",
        created_at=T0,
    )
    project.attach_progress(ProgressId("prog_001"))
    return project


def build_progress() -> Progress:
    progress = Progress(
        progress_id=ProgressId("prog_001"), project_id=ProjectId("proj_001")
    )
    progress.update(
        at(30),
        completion_percentage=45.5,
        knowledge_gained=12.0,
        habit_score=3.5,
        resource_delta=-8.0,
        velocity=1.5,
        estimated_completion=at(10000),
        confidence=0.8,
    )
    return progress


def build_resource() -> Resource:
    resource = Resource(
        resource_id=ResourceId("res_001"),
        user_id=UserId("user_001"),
        type=ResourceType.ENERGY,
        current_value=100.0,
        unit="points",
    )
    resource.consume(30.0, at(10))
    resource.produce(5.0, at(20))
    return resource


def build_knowledge() -> Knowledge:
    knowledge = Knowledge(
        knowledge_id=KnowledgeId("kno_001"),
        user_id=UserId("user_001"),
        domain="Testing",
        topic="ISTQB",
        concept="Test Management",
        project_id=ProjectId("proj_001"),
        difficulty="intermediate",
        source="ISTQB syllabus",
    )
    knowledge.revise(at(10), confidence=62.5)
    knowledge.mark_applied()
    knowledge.update_retention(0.75)
    return knowledge


def build_reflection() -> Reflection:
    return Reflection(
        reflection_id=ReflectionId("ref_001"),
        event_id=EventId("evt_001"),
        context_window_id=ContextWindowId("win_001"),
        created_at=at(130),
        facts="Studied for two hours with one interruption",
        interpretation="Interruptions cost roughly fifteen minutes",
        root_cause="Phone not silenced",
        lesson_learned="Silence phone before study sessions",
        improvement="Enable focus mode",
        confidence=0.9,
    )


def build_insight() -> Insight:
    return Insight(
        insight_id=InsightId("ins_001"),
        source_reflection_id=ReflectionId("ref_001"),
        created_at=at(140),
        category="focus",
        confidence=0.85,
        reusable=True,
    )


def build_habit() -> Habit:
    habit = Habit.infer(
        habit_id=HabitId("hab_001"),
        user_id=UserId("user_001"),
        name="Morning Study",
        detected_at=T0,
        trigger="after breakfast",
        frequency="daily",
        reward="progress feeling",
        strength=40.0,
    )
    habit.update_strength(55.0, at(30))
    return habit


def build_goal() -> Goal:
    goal = Goal(
        goal_id=GoalId("goal_001"),
        user_id=UserId("user_001"),
        name="Continue towards SDET",
        description="Emergent direction from ISTQB project history",
        related_project_ids=(ProjectId("proj_001"), ProjectId("proj_002")),
        confidence_score=0.7,
    )
    goal.accept(at(50))
    return goal
