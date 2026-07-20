"""Daemon lifecycle — a small local state machine.

Implemented with stdlib only: importing the domain state-machine
machinery would violate the daemon's dependency rules (never Domain).
Restart is allowed (Stopped -> Running): the daemon is runtime
orchestration, not historical evidence.
"""

from enum import Enum, unique

from paios.daemon.exceptions import DaemonStateError


@unique
class DaemonState(Enum):
    CREATED = "Created"
    RUNNING = "Running"
    PAUSED = "Paused"
    STOPPING = "Stopping"
    STOPPED = "Stopped"


_ALLOWED: dict[DaemonState, frozenset[DaemonState]] = {
    DaemonState.CREATED: frozenset({DaemonState.RUNNING}),
    DaemonState.RUNNING: frozenset(
        {DaemonState.PAUSED, DaemonState.STOPPING}
    ),
    DaemonState.PAUSED: frozenset(
        {DaemonState.RUNNING, DaemonState.STOPPING}
    ),
    DaemonState.STOPPING: frozenset({DaemonState.STOPPED}),
    DaemonState.STOPPED: frozenset({DaemonState.RUNNING}),  # restart
}


def validate_transition(current: DaemonState, target: DaemonState) -> None:
    if target not in _ALLOWED[current]:
        raise DaemonStateError(
            f"Daemon cannot move {current.value!r} -> {target.value!r}"
        )
