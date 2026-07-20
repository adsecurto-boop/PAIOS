"""State machines and immutable transition history.

A transition appends lifecycle evidence; it never rewrites History
(STATE_MACHINES.md - Purpose and invariants).
"""

from paios.domain.state_machines.machine import (
    StateMachine,
    TransitionHistory,
    TransitionRecord,
)
from paios.domain.state_machines.definitions import (
    CONTEXT_WINDOW_STATE_MACHINE,
    DISTURBER_STATE_MACHINE,
    EVENT_STATE_MACHINE,
    RECOMMENDATION_STATE_MACHINE,
)

__all__ = [
    "CONTEXT_WINDOW_STATE_MACHINE",
    "DISTURBER_STATE_MACHINE",
    "EVENT_STATE_MACHINE",
    "RECOMMENDATION_STATE_MACHINE",
    "StateMachine",
    "TransitionHistory",
    "TransitionRecord",
]
