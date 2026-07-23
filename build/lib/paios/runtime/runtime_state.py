"""Runtime State and the Execution Context hierarchy.

Runtime State is the kernel-owned, mutable, EPHEMERAL "current moment" of
PAIOS (BEHAVIORAL_ARCHITECTURE.md section 5): it evolves continuously
while the system runs and is discarded at shutdown. Historical data is
permanent; Runtime State is not.

Execution Context (approved resolutions C2/C7): the runtime invariant is
"exactly one Execution Context" per running kernel. The context is either

- ``EventExecutionContext`` — a user Event is running (Started/Resumed);
  it references the Event and the Context Window that Event owns; or
- ``IdleExecutionContext`` — no user Event is running (Booting, Waiting,
  Sleeping, Between Events). Runtime-only: never persisted, never
  historical, never visible to repositories, and NOT a domain Event
  aggregate instance. Only EventExecutionContext owns a Context Window.

This keeps the Domain Invariant "exactly one Running Event" at full
strength: the one logical running execution is always represented.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, unique

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
from paios.domain.enums import DisturberState, RecommendationStatus
from paios.domain.value_objects.identifiers import ContextWindowId, EventId
from paios.runtime.exceptions import RuntimeInvariantError

#: Recommendation states that still matter to scheduling decisions
#: (BEHAVIORAL_ARCHITECTURE.md section 5, "Current Recommendations" —
#: active recommendations with acceptance status). Terminal decision
#: evidence (Rejected/Expired/Consumed) is naturally excluded.
ACTIVE_RECOMMENDATION_STATES: frozenset[RecommendationStatus] = frozenset(
    {
        RecommendationStatus.GENERATED,
        RecommendationStatus.PENDING,
        RecommendationStatus.ACCEPTED,
    }
)

#: Disturber states whose lifecycle is not yet complete
#: (BEHAVIORAL_ARCHITECTURE.md section 5, "Current Disturbances" — active
#: Event Disturbers). Resolved/Archived are complete and excluded.
ACTIVE_DISTURBER_STATES: frozenset[DisturberState] = frozenset(
    {
        DisturberState.DETECTED,
        DisturberState.RECORDED,
        DisturberState.ANALYZED,
        DisturberState.APPLIED,
    }
)


@unique
class IdleReason(Enum):
    BOOTING = "Booting"
    WAITING = "Waiting"
    SLEEPING = "Sleeping"
    BETWEEN_EVENTS = "Between Events"


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """The one active execution context of the runtime (immutable value)."""

    since: datetime


@dataclass(frozen=True, slots=True)
class IdleExecutionContext(ExecutionContext):
    """Runtime-only idle execution: no user Event is running.

    Owns NO Context Window (approved resolution C2)."""

    reason: IdleReason = IdleReason.WAITING


@dataclass(frozen=True, slots=True)
class EventExecutionContext(ExecutionContext):
    """A user Event (Started/Resumed) is the running execution.

    References the running Event and the Context Window that Event owns —
    the only execution context that carries a Context Window."""

    event_id: EventId = None  # type: ignore[assignment]
    context_window_id: ContextWindowId = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.event_id is None or self.context_window_id is None:
            raise RuntimeInvariantError(
                "EventExecutionContext requires the running Event and the "
                "Context Window it owns"
            )


class RuntimeState:
    """The kernel-owned current moment. Mutable, ephemeral, never persisted.

    Aggregates loaded at boot are held as immutable tuples — the Kernel
    references domain entities, it does not own them (ownership stays with
    the User per ENTITY_RELATIONSHIPS.md)."""

    def __init__(
        self,
        *,
        current_time: datetime,
        execution_context: ExecutionContext,
        users: tuple[User, ...] = (),
        principles: tuple[Principle, ...] = (),
        contexts: tuple[Context, ...] = (),
        context_windows: tuple[ContextWindow, ...] = (),
        events: tuple[Event, ...] = (),
        projects: tuple[Project, ...] = (),
        progress: tuple[Progress, ...] = (),
        resources: tuple[Resource, ...] = (),
        knowledge: tuple[Knowledge, ...] = (),
        recommendations: tuple[Recommendation, ...] = (),
        event_disturbers: tuple[EventDisturber, ...] = (),
        reflections: tuple[Reflection, ...] = (),
        insights: tuple[Insight, ...] = (),
        habits: tuple[Habit, ...] = (),
        goals: tuple[Goal, ...] = (),
    ) -> None:
        self.current_time = current_time
        self._execution_context = self._validated_context(execution_context)
        self.users = tuple(users)
        self.principles = tuple(principles)
        self.contexts = tuple(contexts)
        self.context_windows = tuple(context_windows)
        self.events = tuple(events)
        self.projects = tuple(projects)
        self.progress = tuple(progress)
        self.resources = tuple(resources)
        self.knowledge = tuple(knowledge)
        self.recommendations = tuple(recommendations)
        self.event_disturbers = tuple(event_disturbers)
        self.reflections = tuple(reflections)
        self.insights = tuple(insights)
        self.habits = tuple(habits)
        self.goals = tuple(goals)

    @staticmethod
    def _validated_context(context: ExecutionContext) -> ExecutionContext:
        if not isinstance(context, ExecutionContext):
            raise RuntimeInvariantError(
                "Runtime invariant violated: exactly one Execution Context "
                "must exist — it is either an EventExecutionContext or an "
                "IdleExecutionContext, never absent"
            )
        return context

    @property
    def execution_context(self) -> ExecutionContext:
        return self._execution_context

    def replace_execution_context(
        self, context: ExecutionContext
    ) -> ExecutionContext:
        """Swap the one Execution Context; returns the previous one."""
        previous = self._execution_context
        self._execution_context = self._validated_context(context)
        return previous

    @property
    def running_context_window_id(self) -> ContextWindowId | None:
        """Only EventExecutionContext owns a Context Window (C2)."""
        if isinstance(self._execution_context, EventExecutionContext):
            return self._execution_context.context_window_id
        return None

    def admit_event(self, event: Event, context_window: ContextWindow) -> None:
        """Admit a newly materialized Event and its owned Context Window
        into Runtime State (Milestone 4 amendment, G1/G6).

        Admission is kernel-owned state management, not domain mutation.
        The pairing is validated both ways; duplicates are rejected."""
        if event.context_window_id != context_window.window_id:
            raise RuntimeInvariantError(
                "Event does not own the supplied Context Window"
            )
        if context_window.event_id != event.event_id:
            raise RuntimeInvariantError(
                "Context Window does not reference the supplied Event"
            )
        if any(existing.event_id == event.event_id for existing in self.events):
            raise RuntimeInvariantError(
                f"Event {event.event_id} is already admitted"
            )
        if any(
            existing.window_id == context_window.window_id
            for existing in self.context_windows
        ):
            raise RuntimeInvariantError(
                f"Context Window {context_window.window_id} is already admitted"
            )
        self.events = self.events + (event,)
        self.context_windows = self.context_windows + (context_window,)

    def admit_recommendation(self, recommendation: Recommendation) -> None:
        """Admit a newly produced Recommendation into Runtime State
        (approved Milestone 6 correction; BEHAVIORAL_ARCHITECTURE.md §5
        'Current Recommendations', §2 'Update Runtime State ->
        Update Recommendations'). Append-only; duplicates rejected."""
        if any(
            existing.recommendation_id == recommendation.recommendation_id
            for existing in self.recommendations
        ):
            raise RuntimeInvariantError(
                f"Recommendation {recommendation.recommendation_id} is "
                "already admitted"
            )
        self.recommendations = self.recommendations + (recommendation,)

    def admit_event_disturber(self, disturber: EventDisturber) -> None:
        """Admit a newly reported Event Disturber into Runtime State
        (approved Milestone 6 correction; BEHAVIORAL_ARCHITECTURE.md §5
        'Current Disturbances'). Append-only; duplicates rejected."""
        if any(
            existing.event_disturber_id == disturber.event_disturber_id
            for existing in self.event_disturbers
        ):
            raise RuntimeInvariantError(
                f"Event Disturber {disturber.event_disturber_id} is "
                "already admitted"
            )
        self.event_disturbers = self.event_disturbers + (disturber,)

    @property
    def active_recommendations(self) -> tuple[Recommendation, ...]:
        """Only Recommendations that still matter to scheduling —
        completed lifecycle objects are naturally excluded."""
        return tuple(
            recommendation
            for recommendation in self.recommendations
            if recommendation.status in ACTIVE_RECOMMENDATION_STATES
        )

    @property
    def active_event_disturbers(self) -> tuple[EventDisturber, ...]:
        """Only Event Disturbers whose lifecycle is not yet complete."""
        return tuple(
            disturber
            for disturber in self.event_disturbers
            if disturber.state in ACTIVE_DISTURBER_STATES
        )

    def aggregate_counts(self) -> dict[str, int]:
        return {
            "users": len(self.users),
            "principles": len(self.principles),
            "contexts": len(self.contexts),
            "context_windows": len(self.context_windows),
            "events": len(self.events),
            "projects": len(self.projects),
            "progress": len(self.progress),
            "resources": len(self.resources),
            "knowledge": len(self.knowledge),
            "recommendations": len(self.recommendations),
            "event_disturbers": len(self.event_disturbers),
            "reflections": len(self.reflections),
            "insights": len(self.insights),
            "habits": len(self.habits),
            "goals": len(self.goals),
        }
