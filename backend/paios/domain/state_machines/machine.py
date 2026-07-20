"""Generic state machine and append-only transition history.

Transitions are recorded, never rewritten. History remains immutable — only
new transition records are added (BUSINESS_RULES.md - Event Lifecycle Rules).
The same machinery serves every lifecycle in the domain: Event, Context
Window, Recommendation, and Event Disturber.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Generic, Mapping, TypeVar

from paios.domain.errors import InvalidTransitionError

S = TypeVar("S", bound=Enum)


@dataclass(frozen=True, slots=True)
class TransitionRecord(Generic[S]):
    """One appended piece of lifecycle evidence.

    ``actor`` is the authority that applied the transition, even when a user
    action or clock condition supplied the trigger (STATE_MACHINES.md).
    """

    from_state: S
    to_state: S
    occurred_at: datetime
    actor: str
    reason: str | None = None


class StateMachine(Generic[S]):
    """A named set of allowed transitions between the states of one Enum."""

    def __init__(self, name: str, transitions: Mapping[S, frozenset[S]]) -> None:
        self._name = name
        self._transitions: dict[S, frozenset[S]] = {
            source: frozenset(targets) for source, targets in transitions.items()
        }

    @property
    def name(self) -> str:
        return self._name

    def allowed_targets(self, state: S) -> frozenset[S]:
        return self._transitions.get(state, frozenset())

    def can_transition(self, from_state: S, to_state: S) -> bool:
        return to_state in self.allowed_targets(from_state)

    def is_terminal(self, state: S) -> bool:
        return not self.allowed_targets(state)

    def validate(self, from_state: S, to_state: S) -> None:
        if not self.can_transition(from_state, to_state):
            raise InvalidTransitionError(
                f"{self._name}: transition {from_state.value!r} -> "
                f"{to_state.value!r} is not permitted"
            )


class TransitionHistory(Generic[S]):
    """Append-only record of every transition an aggregate has undergone.

    The current state is derived from the initial state plus the appended
    records; there is no way to remove or rewrite a record.
    """

    def __init__(self, machine: StateMachine[S], initial_state: S) -> None:
        self._machine = machine
        self._initial_state = initial_state
        self._records: list[TransitionRecord[S]] = []

    @property
    def machine(self) -> StateMachine[S]:
        return self._machine

    @property
    def initial_state(self) -> S:
        return self._initial_state

    @property
    def current_state(self) -> S:
        if self._records:
            return self._records[-1].to_state
        return self._initial_state

    @property
    def records(self) -> tuple[TransitionRecord[S], ...]:
        return tuple(self._records)

    def apply(
        self,
        to_state: S,
        occurred_at: datetime,
        actor: str,
        reason: str | None = None,
    ) -> TransitionRecord[S]:
        """Validate and append one transition; returns the appended record."""
        current = self.current_state
        self._machine.validate(current, to_state)
        record = TransitionRecord(
            from_state=current,
            to_state=to_state,
            occurred_at=occurred_at,
            actor=actor,
            reason=reason,
        )
        self._records.append(record)
        return record
