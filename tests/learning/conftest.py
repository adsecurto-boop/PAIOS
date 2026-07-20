"""History builders for Learning Engine tests — pure domain objects."""

from datetime import datetime, timedelta

from paios.domain.entities.event import Event
from paios.domain.entities.event_disturber import EventDisturber
from paios.domain.entities.habit import Habit
from paios.domain.entities.principle import Principle
from paios.domain.entities.reflection import Reflection
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
    ContextWindowId,
    EventDisturberId,
    EventId,
    HabitId,
    PrincipleId,
    ReflectionId,
    UserId,
)
from paios.domain.value_objects.resource_flow import ResourceFlow
from paios.domain.value_objects.time import Duration
from paios.learning.history import History

T0 = datetime(2026, 7, 1, 9, 0)
USER = UserId("user_001")


def day(offset: int, hour: int = 9) -> datetime:
    return T0 + timedelta(days=offset, hours=hour - 9)


def completed_event(
    event_id: str,
    category: str,
    day_offset: int,
    impact: ImpactType | None = None,
    outcome: EventOutcomeType | None = None,
    duration_minutes: int = 60,
    money_consumed: float = 0.0,
    money_produced: float = 0.0,
    reflection_id: str | None = None,
) -> Event:
    start = day(day_offset)
    end = start + timedelta(minutes=duration_minutes)
    consumed = (
        {ResourceType.MONEY: money_consumed} if money_consumed else {}
    )
    produced = (
        {ResourceType.MONEY: money_produced} if money_produced else {}
    )
    event = Event(
        event_id=EventId(event_id),
        user_id=USER,
        context_window_id=ContextWindowId(f"win_{event_id}"),
        category=category,
        description=f"{category} on day {day_offset}",
        start_time=start,
        end_time=end,
        duration=Duration(duration_minutes),
        impact_type=impact,
        resource_flow=ResourceFlow(consumed=consumed, produced=produced),
        reflection_id=(
            ReflectionId(reflection_id) if reflection_id is not None else None
        ),
    )
    event.transition_to(EventStatus.SCHEDULED, start)
    event.transition_to(EventStatus.READY, start)
    event.transition_to(EventStatus.STARTED, start)
    event.transition_to(EventStatus.COMPLETED, end)
    if outcome is not None:
        event.record_outcome(EventOutcome(outcome, end))
    return event


def skipped_event(event_id: str, category: str, day_offset: int) -> Event:
    moment = day(day_offset)
    event = Event(
        event_id=EventId(event_id),
        user_id=USER,
        context_window_id=ContextWindowId(f"win_{event_id}"),
        category=category,
        description=f"skipped {category}",
    )
    event.transition_to(EventStatus.SCHEDULED, moment)
    event.transition_to(EventStatus.SKIPPED, moment)
    return event


def reflection(
    reflection_id: str,
    event_id: str,
    day_offset: int,
    lesson: str | None = "Do it earlier in the day",
    root_cause: str | None = "Started too late",
) -> Reflection:
    return Reflection(
        reflection_id=ReflectionId(reflection_id),
        event_id=EventId(event_id),
        context_window_id=ContextWindowId(f"win_{event_id}"),
        created_at=day(day_offset),
        lesson_learned=lesson,
        root_cause=root_cause,
        confidence=0.8,
    )


def habit(name: str, habit_id: str = "hab_001", reward: str | None = None) -> Habit:
    return Habit.infer(
        habit_id=HabitId(habit_id),
        user_id=USER,
        name=name,
        detected_at=T0,
        reward=reward,
        strength=50.0,
    )


def principle(name: str, category: PrincipleCategory) -> Principle:
    return Principle(
        principle_id=PrincipleId(f"prin_{name.lower().replace(' ', '_')}"),
        name=name,
        description=name,
        category=category,
        created_at=T0,
    )


def disturber(
    disturber_id: str, disturber_type: DisturberType, day_offset: int
) -> EventDisturber:
    return EventDisturber(
        event_disturber_id=EventDisturberId(disturber_id),
        user_id=USER,
        type=disturber_type,
        description="disturbance",
        severity=DisturberSeverity.MEDIUM,
        occurred_at=day(day_offset),
    )


def smoking_history(first_half: int = 5, second_half: int = 2) -> History:
    """Smoking events across a 14-day window: declining by default."""
    events = [
        completed_event(
            f"evt_smoke_a{i}", "smoking", i, impact=ImpactType.DISTRACTION
        )
        for i in range(first_half)
    ]
    events += [
        completed_event(
            f"evt_smoke_b{i}", "smoking", 8 + i, impact=ImpactType.DISTRACTION
        )
        for i in range(second_half)
    ]
    # Anchor the window at day 14 so halves split at day 7.
    events.append(completed_event("evt_anchor", "misc", 14))
    return History(events=tuple(events))
