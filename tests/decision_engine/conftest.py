"""Snapshot builders for Decision Engine tests.

Snapshots are constructed directly — the engine is pure, so no kernel,
repositories, or clock are needed to test it.
"""

from datetime import datetime, timedelta

from paios.domain.entities.context import Context
from paios.domain.entities.event import Event
from paios.domain.entities.goal import Goal
from paios.domain.entities.habit import Habit
from paios.domain.entities.knowledge import Knowledge
from paios.domain.entities.principle import Principle
from paios.domain.entities.progress import Progress
from paios.domain.entities.project import Project
from paios.domain.entities.recommendation import Recommendation
from paios.domain.entities.resource import Resource
from paios.domain.enums import (
    EventStatus,
    ImpactType,
    PrincipleCategory,
    ResourceType,
)
from paios.domain.value_objects.identifiers import (
    ContextId,
    ContextWindowId,
    EventId,
    GoalId,
    HabitId,
    KnowledgeId,
    PrincipleId,
    ProgressId,
    ProjectId,
    RecommendationId,
    ResourceId,
    UserId,
)
from paios.runtime.runtime_snapshot import RuntimeSnapshot
from paios.runtime.runtime_state import IdleExecutionContext

T0 = datetime(2026, 7, 21, 9, 0)
USER = UserId("user_001")


def at(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


def make_snapshot(**overrides) -> RuntimeSnapshot:
    fields = dict(
        created_at=T0,
        current_time=T0,
        execution_context=IdleExecutionContext(since=T0),
        running_event=None,
        running_context_window=None,
        principles=(),
        contexts=(),
        context_windows=(),
        events=(),
        projects=(),
        progress=(),
        resources=(),
        knowledge=(),
        recommendations=(),
        event_disturbers=(),
        reflections=(),
        insights=(),
        habits=(),
        goals=(),
    )
    fields.update(overrides)
    return RuntimeSnapshot(**fields)


def principle(pid: str, name: str, category: PrincipleCategory) -> Principle:
    return Principle(
        principle_id=PrincipleId(pid),
        name=name,
        description=name,
        category=category,
        created_at=T0,
    )


def standard_principles() -> tuple[Principle, ...]:
    return (
        principle("prin_health", "Protect Health", PrincipleCategory.HEALTH),
        principle(
            "prin_resp", "Fulfill Responsibilities", PrincipleCategory.RESPONSIBILITY
        ),
        principle("prin_learn", "Learn Continuously", PrincipleCategory.LEARNING),
    )


def event_in_state(
    event_id: str,
    status: EventStatus,
    category: str = "study",
    impact: ImpactType | None = None,
) -> Event:
    event = Event(
        event_id=EventId(event_id),
        user_id=USER,
        context_window_id=ContextWindowId(f"win_{event_id}"),
        category=category,
        description=f"Event {event_id}",
        impact_type=impact,
        start_time=T0,
    )
    paths = {
        EventStatus.STARTED: (
            EventStatus.SCHEDULED,
            EventStatus.READY,
            EventStatus.STARTED,
        ),
        EventStatus.PAUSED: (
            EventStatus.SCHEDULED,
            EventStatus.READY,
            EventStatus.STARTED,
            EventStatus.PAUSED,
        ),
        EventStatus.INTERRUPTED: (
            EventStatus.SCHEDULED,
            EventStatus.READY,
            EventStatus.STARTED,
            EventStatus.INTERRUPTED,
        ),
        EventStatus.COMPLETED: (
            EventStatus.SCHEDULED,
            EventStatus.READY,
            EventStatus.STARTED,
            EventStatus.COMPLETED,
        ),
        EventStatus.SCHEDULED: (EventStatus.SCHEDULED,),
    }
    for index, target in enumerate(paths[status], start=1):
        event.transition_to(target, at(index))
    return event


def energy_resource(value: float, rid: str = "res_energy") -> Resource:
    return Resource(
        resource_id=ResourceId(rid),
        user_id=USER,
        type=ResourceType.ENERGY,
        current_value=value,
        unit="points",
    )


def knowledge_gap(confidence: float = 20.0, kid: str = "kno_gap") -> Knowledge:
    return Knowledge(
        knowledge_id=KnowledgeId(kid),
        user_id=USER,
        domain="Testing",
        topic="ISTQB",
        concept="Test Management",
        confidence=confidence,
        project_id=ProjectId("proj_001"),
    )


def active_project_with_progress(
    completion: float = 40.0,
) -> tuple[Project, Progress, Goal]:
    project = Project(
        project_id=ProjectId("proj_001"),
        user_id=USER,
        name="ISTQB Certification",
        description="Complete ISTQB Foundation Level",
        created_at=T0,
        progress_id=ProgressId("prog_001"),
    )
    progress = Progress(
        progress_id=ProgressId("prog_001"),
        project_id=ProjectId("proj_001"),
        completion_percentage=completion,
    )
    goal = Goal(
        goal_id=GoalId("goal_001"),
        user_id=USER,
        name="Become SDET",
        description="Emergent direction",
        related_project_ids=(ProjectId("proj_001"),),
    )
    goal.accept(at(1))
    return project, progress, goal


def strong_habit(strength: float = 70.0) -> Habit:
    return Habit.infer(
        habit_id=HabitId("hab_001"),
        user_id=USER,
        name="Morning Study",
        detected_at=T0,
        strength=strength,
    )


def pending_recommendation(reason: str, rid: str = "rec_prev") -> Recommendation:
    recommendation = Recommendation(
        recommendation_id=RecommendationId(rid),
        user_id=USER,
        reason=reason,
        created_at=at(-30),
        expires_at=at(60),
    )
    recommendation.present(at(-29))
    return recommendation


def full_snapshot() -> RuntimeSnapshot:
    """A rich snapshot exercising every rule at once."""
    project, progress, goal = active_project_with_progress()
    return make_snapshot(
        principles=standard_principles(),
        events=(
            event_in_state("evt_paused", EventStatus.PAUSED),
            event_in_state(
                "evt_done",
                EventStatus.COMPLETED,
                impact=ImpactType.OPPORTUNITY,
            ),
        ),
        resources=(energy_resource(20.0),),
        knowledge=(knowledge_gap(),),
        projects=(project,),
        progress=(progress,),
        goals=(goal,),
        habits=(strong_habit(),),
        contexts=(
            Context(context_id=ContextId("ctx_001"), name="Office", created_at=T0),
        ),
    )
