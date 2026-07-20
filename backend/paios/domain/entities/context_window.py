"""Context Window — a single, time-bounded activation of a Context.

Owned by exactly one Event; references exactly one Context
(BUSINESS_RULES.md - Context Window Rules). Same Context, different Context
Window (DOMAIN_MODEL.md Principle 17). Lifecycle per STATE_MACHINES.md
section 3: Created -> Active -> Changing -> Expired -> Archived, with
Active -> Expired also valid. Invalid: Created -> Expired, Expired -> Active,
Archived -> Active — all rejected by the state machine.

Lifecycle transitions are applied by the Runtime (STATE_MACHINES.md actor
column); the domain records the actor on every transition.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar

from paios.domain.entities.base import Entity
from paios.domain.enums import ContextWindowState
from paios.domain.errors import DomainValidationError, ImmutabilityViolationError
from paios.domain.state_machines.definitions import CONTEXT_WINDOW_STATE_MACHINE
from paios.domain.state_machines.machine import TransitionHistory, TransitionRecord
from paios.domain.value_objects.identifiers import ContextId, ContextWindowId, EventId
from paios.domain.value_objects.time import Duration

_DEFAULT_ACTOR = "Runtime"

#: Past Context Windows are immutable (RUNTIME_EXECUTION.md - Core
#: Guarantees); facts freeze once the window is Expired or Archived.
_IMMUTABLE_STATES: frozenset[ContextWindowState] = frozenset(
    {ContextWindowState.EXPIRED, ContextWindowState.ARCHIVED}
)

_FACT_FIELDS: frozenset[str] = frozenset(
    {
        "context_id",
        "event_id",
        "start_time",
        "end_time",
        "duration",
        "reason_started",
        "reason_ended",
    }
)


@dataclass(eq=False)
class ContextWindow(Entity):
    _id_attr: ClassVar[str] = "window_id"

    window_id: ContextWindowId
    context_id: ContextId
    event_id: EventId
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration: Duration | None = None
    reason_started: str | None = None
    reason_ended: str | None = None
    _history: TransitionHistory[ContextWindowState] = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        self._history = TransitionHistory(
            CONTEXT_WINDOW_STATE_MACHINE, ContextWindowState.CREATED
        )

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_history" and "_history" in self.__dict__:
            raise ImmutabilityViolationError(
                "Context Window transition history cannot be replaced; "
                "transitions are recorded, never rewritten"
            )
        if name in _FACT_FIELDS and self._facts_frozen():
            raise ImmutabilityViolationError(
                f"Context Window {self.window_id} is "
                f"{self.current_state.value!r}; past Context Windows are "
                f"immutable and {name!r} can no longer change"
            )
        super().__setattr__(name, value)

    def _facts_frozen(self) -> bool:
        history = self.__dict__.get("_history")
        return history is not None and history.current_state in _IMMUTABLE_STATES

    @classmethod
    def restore(
        cls,
        *,
        window_id: ContextWindowId,
        context_id: ContextId,
        event_id: EventId,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        duration: Duration | None = None,
        reason_started: str | None = None,
        reason_ended: str | None = None,
        transitions: tuple[TransitionRecord[ContextWindowState], ...] = (),
    ) -> "ContextWindow":
        """Reconstitute a Context Window from persisted evidence.

        Facts are supplied while the fresh instance is still Created, then
        the structurally validated history is attached — so a window whose
        evidence reaches Expired/Archived is fact-frozen from the moment the
        factory returns ("past Context Windows are immutable"). No lifecycle
        command is re-executed and no closing fact is re-derived.
        """
        window = cls(
            window_id=window_id,
            context_id=context_id,
            event_id=event_id,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            reason_started=reason_started,
            reason_ended=reason_ended,
        )
        history = TransitionHistory.from_records(
            CONTEXT_WINDOW_STATE_MACHINE, ContextWindowState.CREATED, transitions
        )
        object.__setattr__(window, "_history", history)
        return window

    @property
    def current_state(self) -> ContextWindowState:
        return self._history.current_state

    @property
    def transitions(self) -> tuple[TransitionRecord[ContextWindowState], ...]:
        return self._history.records

    @property
    def is_active(self) -> bool:
        return self.current_state is ContextWindowState.ACTIVE

    def activate(
        self,
        at: datetime,
        reason_started: str | None = None,
        actor: str = _DEFAULT_ACTOR,
    ) -> TransitionRecord[ContextWindowState]:
        record = self._history.apply(
            ContextWindowState.ACTIVE, at, actor, reason_started
        )
        if self.start_time is None:
            self.start_time = at
        if reason_started is not None:
            self.reason_started = reason_started
        return record

    def mark_changing(
        self,
        at: datetime,
        reason: str | None = None,
        actor: str = _DEFAULT_ACTOR,
    ) -> TransitionRecord[ContextWindowState]:
        return self._history.apply(ContextWindowState.CHANGING, at, actor, reason)

    def expire(
        self,
        at: datetime,
        reason_ended: str | None = None,
        actor: str = _DEFAULT_ACTOR,
    ) -> TransitionRecord[ContextWindowState]:
        # Facts freeze the moment the window is Expired, so the closing facts
        # must be written before the transition — after validating it is legal.
        CONTEXT_WINDOW_STATE_MACHINE.validate(
            self.current_state, ContextWindowState.EXPIRED
        )
        end_time = self.end_time if self.end_time is not None else at
        if self.start_time is not None and end_time < self.start_time:
            raise DomainValidationError(
                "Context Window cannot end before it started"
            )
        if self.end_time is None:
            self.end_time = end_time
        if reason_ended is not None:
            self.reason_ended = reason_ended
        if self.duration is None and self.start_time is not None:
            self.duration = Duration.between(self.start_time, self.end_time)
        return self._history.apply(
            ContextWindowState.EXPIRED, at, actor, reason_ended
        )

    def archive(
        self, at: datetime, actor: str = _DEFAULT_ACTOR
    ) -> TransitionRecord[ContextWindowState]:
        return self._history.apply(ContextWindowState.ARCHIVED, at, actor, None)
