"""Kernel lifecycle state machine (approved resolution C3).

No canonical document defines a kernel state machine; this one implements
the mission-specified boot and shutdown sequences using the same
state-machine machinery as every domain lifecycle. Paused means "not
accepting work" — History never stops existing and is never touched.
"""

from enum import Enum, unique

from paios.domain.state_machines.machine import StateMachine


@unique
class KernelState(Enum):
    CREATED = "Created"
    BOOTING = "Booting"
    READY = "Ready"
    RUNNING = "Running"
    PAUSED = "Paused"
    STOPPING = "Stopping"
    STOPPED = "Stopped"
    FAILED = "Failed"


KERNEL_STATE_MACHINE: StateMachine[KernelState] = StateMachine(
    "Kernel Lifecycle",
    {
        KernelState.CREATED: frozenset({KernelState.BOOTING}),
        KernelState.BOOTING: frozenset({KernelState.READY, KernelState.FAILED}),
        KernelState.READY: frozenset({KernelState.RUNNING, KernelState.STOPPING}),
        KernelState.RUNNING: frozenset(
            {KernelState.PAUSED, KernelState.STOPPING}
        ),
        KernelState.PAUSED: frozenset(
            {KernelState.RUNNING, KernelState.STOPPING}
        ),
        KernelState.STOPPING: frozenset({KernelState.STOPPED}),
        KernelState.STOPPED: frozenset(),
        KernelState.FAILED: frozenset(),
    },
)

#: States in which the kernel holds runtime state and can serve queries.
OPERATIONAL_STATES: frozenset[KernelState] = frozenset(
    {KernelState.READY, KernelState.RUNNING, KernelState.PAUSED}
)
