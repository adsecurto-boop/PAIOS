"""Runtime Snapshot — the immutable view reasoning consumers receive.

The Decision Engine will NEVER access repositories: it receives Runtime
Snapshots assembled by the Kernel (DECISION_ENGINE.md section 2 — "unified
Runtime State snapshot ... single source of truth").

Contents follow approved resolution C1: the mission list plus Principles,
Contexts, Progress, Event Disturbers, and historical Events (which carry
Impact classifications), with Context Windows included as Event history
evidence. Scheduler State arrives with the Scheduler (Milestone 4); Domain
Policies and User Preferences are not domain entities and are deferred.

Immutability is structural: the snapshot is a frozen container of tuples.
The domain entities it references carry their own immutability guards
(post-execution Events and past Context Windows are fact-frozen).
"""

from dataclasses import dataclass
from datetime import datetime

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
from paios.runtime.clock import Clock
from paios.runtime.runtime_state import (
    EventExecutionContext,
    ExecutionContext,
    RuntimeState,
)


@dataclass(frozen=True)
class RuntimeSnapshot:
    """One immutable, point-in-time view of the runtime for reasoning."""

    created_at: datetime
    current_time: datetime
    execution_context: ExecutionContext
    running_event: Event | None
    running_context_window: ContextWindow | None
    principles: tuple[Principle, ...]
    contexts: tuple[Context, ...]
    context_windows: tuple[ContextWindow, ...]
    events: tuple[Event, ...]
    projects: tuple[Project, ...]
    progress: tuple[Progress, ...]
    resources: tuple[Resource, ...]
    knowledge: tuple[Knowledge, ...]
    recommendations: tuple[Recommendation, ...]
    event_disturbers: tuple[EventDisturber, ...]
    reflections: tuple[Reflection, ...]
    insights: tuple[Insight, ...]
    habits: tuple[Habit, ...]
    goals: tuple[Goal, ...]


class SnapshotManager:
    """Assembles immutable snapshots from the kernel-owned Runtime State."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._latest: RuntimeSnapshot | None = None

    @property
    def latest(self) -> RuntimeSnapshot | None:
        return self._latest

    def clear(self) -> None:
        self._latest = None

    def create(self, state: RuntimeState) -> RuntimeSnapshot:
        execution_context = state.execution_context
        running_event: Event | None = None
        running_window: ContextWindow | None = None
        if isinstance(execution_context, EventExecutionContext):
            running_event = next(
                (
                    event
                    for event in state.events
                    if event.event_id == execution_context.event_id
                ),
                None,
            )
            running_window = next(
                (
                    window
                    for window in state.context_windows
                    if window.window_id == execution_context.context_window_id
                ),
                None,
            )
        snapshot = RuntimeSnapshot(
            created_at=self._clock.now(),
            current_time=state.current_time,
            execution_context=execution_context,
            running_event=running_event,
            running_context_window=running_window,
            principles=state.principles,
            contexts=state.contexts,
            context_windows=state.context_windows,
            events=state.events,
            projects=state.projects,
            progress=state.progress,
            resources=state.resources,
            knowledge=state.knowledge,
            recommendations=state.recommendations,
            event_disturbers=state.event_disturbers,
            reflections=state.reflections,
            insights=state.insights,
            habits=state.habits,
            goals=state.goals,
        )
        self._latest = snapshot
        return snapshot
