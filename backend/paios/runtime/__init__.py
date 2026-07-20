"""PAIOS Runtime Kernel (Milestone 3).

The central orchestrator of PAIOS runtime (BEHAVIORAL_ARCHITECTURE.md
section 4): owns Runtime State, the runtime lifecycle (boot/shutdown),
immutable Runtime Snapshots, the System Event Bus, the Clock abstraction,
Runtime Status, the Service Registry, invariant enforcement, and the
Idle Execution Context.

The Kernel observes, holds, validates, and broadcasts — it never decides.
It schedules nothing (Scheduler, Milestone 4), reasons about nothing
(Decision Engine, Milestone 5), learns nothing, and persists nothing
(repositories are reached only through injected interfaces, only at boot).
"""

from paios.runtime.clock import Clock, ManualClock, SystemClock
from paios.runtime.event_bus import EventBus
from paios.runtime.exceptions import (
    BootError,
    KernelLifecycleError,
    RuntimeInvariantError,
    RuntimeKernelError,
    ServiceRegistryError,
)
from paios.runtime.kernel import RepositoryProvider, RuntimeKernel
from paios.runtime.lifecycle import KernelState
from paios.runtime.runtime_snapshot import RuntimeSnapshot, SnapshotManager
from paios.runtime.runtime_state import (
    EventExecutionContext,
    ExecutionContext,
    IdleExecutionContext,
    IdleReason,
    RuntimeState,
)
from paios.runtime.runtime_status import RuntimeStatus
from paios.runtime.services import InvariantChecker, ServiceRegistry
from paios.runtime.system_events import SystemEvent, SystemEventType

__all__ = [
    "BootError",
    "Clock",
    "EventBus",
    "EventExecutionContext",
    "ExecutionContext",
    "IdleExecutionContext",
    "IdleReason",
    "InvariantChecker",
    "KernelLifecycleError",
    "KernelState",
    "ManualClock",
    "RepositoryProvider",
    "RuntimeInvariantError",
    "RuntimeKernel",
    "RuntimeKernelError",
    "RuntimeSnapshot",
    "RuntimeState",
    "RuntimeStatus",
    "ServiceRegistry",
    "ServiceRegistryError",
    "SnapshotManager",
    "SystemClock",
    "SystemEvent",
    "SystemEventType",
]
