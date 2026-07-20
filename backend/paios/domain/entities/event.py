"""Event — the single aggregate at the center of PAIOS.

There is exactly ONE Event aggregate (approved Resolution 2). A "Scheduled
Event" is simply an Event in the Scheduled lifecycle state; no ScheduledEvent,
Task, or Todo entity exists (ADR-001, DOMAIN_MODEL.md Principle 2).

Lifecycle: the twelve canonical states of DOMAIN_MODEL.md Principle 19,
transitioning only along the formal table of STATE_MACHINES.md section 1.
The Scheduler controls all Event state transitions — an Event never
transitions itself (BUSINESS_RULES.md); the domain records the acting
authority on every transition and defaults it to "Scheduler".

Immutability guarantees enforced here (BUSINESS_RULES.md - Domain Invariants):
- Event IDs are immutable once assigned.
- Transitions are recorded, never rewritten (append-only TransitionHistory).
- Once an Event reaches a post-execution state (Completed, Skipped,
  Cancelled, Overtaken, Archived) its historical facts are frozen. The only
  evidence that may still be recorded is the Outcome (once) and a Reflection
  link (once) — both are new evidence about History, not edits of it
  (STATE_MACHINES.md - Event outcome; DOMAIN_MODEL.md - Context vs Reflection).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar

from paios.domain.entities.base import Entity
from paios.domain.enums import RUNNING_STATES, EventStatus, ImpactType
from paios.domain.errors import (
    DomainValidationError,
    ImmutabilityViolationError,
)
from paios.domain.state_machines.definitions import EVENT_STATE_MACHINE
from paios.domain.state_machines.machine import TransitionHistory, TransitionRecord
from paios.domain.value_objects.event_outcome import EventOutcome
from paios.domain.value_objects.identifiers import (
    ContextWindowId,
    EventId,
    ProjectId,
    ReflectionId,
    UserId,
)
from paios.domain.value_objects.resource_flow import ResourceFlow
from paios.domain.value_objects.time import Duration

#: States after which the Event's historical facts may no longer change.
POST_EXECUTION_STATES: frozenset[EventStatus] = frozenset(
    {
        EventStatus.COMPLETED,
        EventStatus.SKIPPED,
        EventStatus.CANCELLED,
        EventStatus.OVERTAKEN,
        EventStatus.ARCHIVED,
    }
)

#: States in which recording an execution Outcome is meaningful: execution
#: ended (Completed), or was abandoned/replaced after possible partial
#: execution (Cancelled, Overtaken). A Skipped Event never executed, so it
#: carries no Outcome (STATE_MACHINES.md - Event outcome).
_OUTCOME_STATES: frozenset[EventStatus] = frozenset(
    {EventStatus.COMPLETED, EventStatus.CANCELLED, EventStatus.OVERTAKEN}
)

#: Historical-fact fields frozen once the Event is post-execution.
_FACT_FIELDS: frozenset[str] = frozenset(
    {
        "user_id",
        "project_id",
        "context_window_id",
        "start_time",
        "end_time",
        "duration",
        "category",
        "description",
        "impact_type",
        "priority_alignment_score",
        "resource_flow",
        "expected_outcome",
        "actual_outcome",
    }
)

_DEFAULT_ACTOR = "Scheduler"


@dataclass(eq=False)
class Event(Entity):
    _id_attr: ClassVar[str] = "event_id"

    event_id: EventId
    user_id: UserId
    context_window_id: ContextWindowId
    category: str
    description: str
    project_id: ProjectId | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration: Duration | None = None
    impact_type: ImpactType | None = None
    priority_alignment_score: int | None = None
    resource_flow: ResourceFlow = field(default_factory=ResourceFlow.empty)
    expected_outcome: str | None = None
    actual_outcome: str | None = None
    reflection_id: ReflectionId | None = None
    _outcome: EventOutcome | None = field(init=False, default=None, repr=False)
    _history: TransitionHistory[EventStatus] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.category.strip():
            raise DomainValidationError("Event requires a category")
        if not self.description.strip():
            raise DomainValidationError("Event requires a description")
        self._history = TransitionHistory(
            EVENT_STATE_MACHINE, EventStatus.RECOMMENDED
        )

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "event_id" and "event_id" in self.__dict__:
            raise ImmutabilityViolationError(
                "Event IDs are immutable once assigned"
            )
        if name == "_history" and "_history" in self.__dict__:
            raise ImmutabilityViolationError(
                "Event transition history cannot be replaced; transitions "
                "are recorded, never rewritten"
            )
        if name in _FACT_FIELDS and self._facts_frozen():
            raise ImmutabilityViolationError(
                f"Event {self.event_id} is in post-execution state "
                f"{self.status.value!r}; historical fact {name!r} is immutable. "
                "Corrections require a new corrective Event."
            )
        if name == "priority_alignment_score" and value is not None:
            if not isinstance(value, int) or isinstance(value, bool):
                raise DomainValidationError(
                    "Priority Alignment Score must be an integer"
                )
            if not 0 <= value <= 10:
                raise DomainValidationError(
                    "Priority Alignment Score must be between 0 and 10"
                )
        if name == "reflection_id" and value is not None:
            existing = self.__dict__.get("reflection_id")
            if existing is not None and existing != value:
                raise ImmutabilityViolationError(
                    "A Reflection, once linked, cannot be replaced"
                )
        super().__setattr__(name, value)

    def _facts_frozen(self) -> bool:
        history = self.__dict__.get("_history")
        return history is not None and history.current_state in POST_EXECUTION_STATES

    # --- Reconstitution (hydration) --------------------------------------

    @classmethod
    def restore(
        cls,
        *,
        event_id: EventId,
        user_id: UserId,
        context_window_id: ContextWindowId,
        category: str,
        description: str,
        project_id: ProjectId | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        duration: Duration | None = None,
        impact_type: ImpactType | None = None,
        priority_alignment_score: int | None = None,
        resource_flow: ResourceFlow | None = None,
        expected_outcome: str | None = None,
        actual_outcome: str | None = None,
        reflection_id: ReflectionId | None = None,
        transitions: tuple[TransitionRecord[EventStatus], ...] = (),
        outcome: EventOutcome | None = None,
    ) -> "Event":
        """Reconstitute an Event from persisted evidence (DDD reconstitution
        factory). Loading restores evidence; it never re-executes commands.

        The transition chain is validated structurally by
        TransitionHistory.from_records. Evidence-shape rules replace command
        preconditions: an Outcome is admissible only if the history passed
        THROUGH an outcome-permitting state (Completed/Cancelled/Overtaken —
        it may since have Archived); a Reflection link only if the history
        reached Completed or Archived. The history is attached while the
        instance is still factory-private with an empty fresh history — the
        public reassignment guard continues to protect every escaped
        instance, and all fact-freeze guards apply from here on.
        """
        event = cls(
            event_id=event_id,
            user_id=user_id,
            context_window_id=context_window_id,
            category=category,
            description=description,
            project_id=project_id,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            impact_type=impact_type,
            priority_alignment_score=priority_alignment_score,
            resource_flow=(
                resource_flow if resource_flow is not None else ResourceFlow.empty()
            ),
            expected_outcome=expected_outcome,
            actual_outcome=actual_outcome,
            reflection_id=reflection_id,
        )
        history = TransitionHistory.from_records(
            EVENT_STATE_MACHINE, EventStatus.RECOMMENDED, transitions
        )
        object.__setattr__(event, "_history", history)
        visited = {record.to_state for record in history.records}
        if reflection_id is not None and not (
            visited & {EventStatus.COMPLETED, EventStatus.ARCHIVED}
        ):
            raise DomainValidationError(
                "Reflection evidence requires a history that reached "
                "Completed or Archived"
            )
        if outcome is not None:
            if not (visited & _OUTCOME_STATES):
                raise DomainValidationError(
                    "Outcome evidence requires a history that passed through "
                    "Completed, Cancelled, or Overtaken"
                )
            event._outcome = outcome
        return event

    # --- Lifecycle -------------------------------------------------------

    @property
    def status(self) -> EventStatus:
        return self._history.current_state

    @property
    def transitions(self) -> tuple[TransitionRecord[EventStatus], ...]:
        return self._history.records

    @property
    def is_running(self) -> bool:
        """Running is a runtime concept: Started or Resumed (GLOSSARY.md)."""
        return self.status in RUNNING_STATES

    def transition_to(
        self,
        to_state: EventStatus,
        at: datetime,
        actor: str = _DEFAULT_ACTOR,
        reason: str | None = None,
    ) -> TransitionRecord[EventStatus]:
        """Apply a Scheduler-controlled lifecycle transition.

        Validates against the formal Event state machine and appends an
        immutable TransitionRecord. History is never rewritten.
        """
        return self._history.apply(to_state, at, actor, reason)

    # --- Post-execution evidence ----------------------------------------

    @property
    def outcome(self) -> EventOutcome | None:
        return self._outcome

    def record_outcome(self, outcome: EventOutcome) -> None:
        """Record immutable execution evidence, exactly once.

        Permitted only after execution ended: Completed, or Cancelled /
        Overtaken after partial execution. Outcome never alters Event History.
        """
        if self._outcome is not None:
            raise ImmutabilityViolationError(
                "Event Outcome is immutable evidence and is already recorded"
            )
        if self.status not in _OUTCOME_STATES:
            raise DomainValidationError(
                f"Outcome cannot be recorded in state {self.status.value!r}; "
                "it requires Completed, Cancelled, or Overtaken"
            )
        self._outcome = outcome

    def link_reflection(self, reflection_id: ReflectionId) -> None:
        """Link the single optional Reflection, once, after completion.

        Learning only occurs from completed history
        (BEHAVIORAL_ARCHITECTURE.md - Behavioral Principles).
        """
        if self.status not in (EventStatus.COMPLETED, EventStatus.ARCHIVED):
            raise DomainValidationError(
                "A Reflection requires a Completed Event"
            )
        if self.reflection_id is not None:
            raise ImmutabilityViolationError(
                "A Reflection, once linked, cannot be replaced"
            )
        self.reflection_id = reflection_id
