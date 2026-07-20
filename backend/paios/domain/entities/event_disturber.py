"""Event Disturber — an unexpected situation that interrupts the plan.

The mandatory chain (DOMAIN_MODEL.md Principle 24; BUSINESS_RULES.md):

    Event Disturber -> Context Window transition -> Scheduler recalculates
    -> Event State Transition

An Event Disturber never modifies an Event directly. Structurally, this
entity carries NO reference to an Event's mutable fields — only the resulting
Context Window transition and an evidential record of which Scheduled Event
IDs were affected (BUSINESS_RULES.md - Domain Invariants: "An Event Disturber
never has a direct foreign key to an Event's mutable fields").

Lifecycle (STATE_MACHINES.md section 5): Detected -> Recorded -> Analyzed ->
Applied -> Resolved -> Archived. Detected -> Applied is invalid — the state
machine enforces the full chain.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar

from paios.domain.entities.base import Entity
from paios.domain.enums import (
    DisturberResolutionStatus,
    DisturberSeverity,
    DisturberState,
    DisturberType,
)
from paios.domain.errors import DomainValidationError, ImmutabilityViolationError
from paios.domain.state_machines.definitions import DISTURBER_STATE_MACHINE
from paios.domain.state_machines.machine import TransitionHistory, TransitionRecord
from paios.domain.value_objects.identifiers import (
    ContextWindowId,
    EventDisturberId,
    EventId,
    UserId,
)

_DEFAULT_ACTOR = "Runtime"


@dataclass(eq=False)
class EventDisturber(Entity):
    _id_attr: ClassVar[str] = "event_disturber_id"

    event_disturber_id: EventDisturberId
    user_id: UserId
    type: DisturberType
    description: str
    severity: DisturberSeverity
    occurred_at: datetime
    resulting_context_window_id: ContextWindowId | None = None
    affected_scheduled_event_ids: tuple[EventId, ...] = ()
    resolution_status: DisturberResolutionStatus = DisturberResolutionStatus.PENDING
    _history: TransitionHistory[DisturberState] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.description.strip():
            raise DomainValidationError("Event Disturber requires a description")
        self._history = TransitionHistory(
            DISTURBER_STATE_MACHINE, DisturberState.DETECTED
        )

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_history" and "_history" in self.__dict__:
            raise ImmutabilityViolationError(
                "Event Disturber transition history cannot be replaced; "
                "transitions append evidence, never rewrite it"
            )
        super().__setattr__(name, value)

    @property
    def state(self) -> DisturberState:
        return self._history.current_state

    @property
    def transitions(self) -> tuple[TransitionRecord[DisturberState], ...]:
        return self._history.records

    def record(
        self, at: datetime, actor: str = _DEFAULT_ACTOR
    ) -> TransitionRecord[DisturberState]:
        return self._history.apply(DisturberState.RECORDED, at, actor, None)

    def analyze(
        self, at: datetime, actor: str = _DEFAULT_ACTOR
    ) -> TransitionRecord[DisturberState]:
        return self._history.apply(DisturberState.ANALYZED, at, actor, None)

    def apply(
        self,
        at: datetime,
        resulting_context_window_id: ContextWindowId,
        actor: str = _DEFAULT_ACTOR,
    ) -> TransitionRecord[DisturberState]:
        """The Disturber's impact becomes a Context Window transition —
        never a direct Event mutation."""
        record = self._history.apply(DisturberState.APPLIED, at, actor, None)
        self.resulting_context_window_id = resulting_context_window_id
        return record

    def resolve(
        self, at: datetime, actor: str = "Scheduler"
    ) -> TransitionRecord[DisturberState]:
        """The Scheduler's recalculation response is established
        (STATE_MACHINES.md section 5: actor for Applied -> Resolved)."""
        record = self._history.apply(DisturberState.RESOLVED, at, actor, None)
        self.resolution_status = DisturberResolutionStatus.RESOLVED
        return record

    def archive(
        self, at: datetime, actor: str = _DEFAULT_ACTOR
    ) -> TransitionRecord[DisturberState]:
        return self._history.apply(DisturberState.ARCHIVED, at, actor, None)
