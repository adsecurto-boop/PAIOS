"""System Events: the runtime communication vocabulary.

Two catalogs coexist by approved resolution C4:

- KERNEL_EVENTS — the Milestone 3 kernel lifecycle events, published by the
  Runtime Kernel itself.
- RESERVED_EVENTS — the BEHAVIORAL_ARCHITECTURE.md section 12 catalog.
  Declared now so the vocabulary is stable; their publishers arrive with
  later milestones (Scheduler, Decision Engine, Learning). The Kernel
  broadcasts them but does not originate them in Milestone 3.

The Runtime Kernel publishes; components subscribe; no component calls
another directly (loose coupling — BEHAVIORAL_ARCHITECTURE.md section 12).
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, unique
from types import MappingProxyType
from typing import Mapping


@unique
class SystemEventType(Enum):
    # --- Kernel events (published in Milestone 3) ------------------------
    KERNEL_BOOTED = "KernelBooted"
    KERNEL_SHUTDOWN = "KernelShutdown"
    RUNTIME_READY = "RuntimeReady"
    RUNTIME_PAUSED = "RuntimePaused"
    RUNTIME_RESUMED = "RuntimeResumed"
    SNAPSHOT_CREATED = "SnapshotCreated"
    SNAPSHOT_UPDATED = "SnapshotUpdated"
    RUNNING_EVENT_CHANGED = "RunningEventChanged"
    RUNNING_CONTEXT_CHANGED = "RunningContextChanged"
    SERVICE_REGISTERED = "ServiceRegistered"
    SERVICE_REMOVED = "ServiceRemoved"

    # --- Scheduler events (Milestone 4, approved refinement 1) -----------
    SCHEDULER_RECALCULATION_REQUESTED = "SchedulerRecalculationRequested"

    # --- Reserved events (publishers arrive in Milestone 4+) -------------
    CONTEXT_CHANGED = "ContextChanged"
    EVENT_STATE_CHANGED = "EventStateChanged"
    RESOURCE_THRESHOLD_CROSSED = "ResourceThresholdCrossed"
    DISTURBANCE_DETECTED = "DisturbanceDetected"
    TIME_PROGRESSED = "TimeProgressed"
    RECOMMENDATION_GENERATED = "RecommendationGenerated"
    PLAN_UPDATED = "PlanUpdated"
    EVENT_COMPLETED = "EventCompleted"
    REFLECTION_CREATED = "ReflectionCreated"
    INSIGHT_GENERATED = "InsightGenerated"
    HABIT_DETECTED = "HabitDetected"


#: Events the Runtime Kernel itself publishes in Milestone 3.
KERNEL_EVENTS: frozenset[SystemEventType] = frozenset(
    {
        SystemEventType.KERNEL_BOOTED,
        SystemEventType.KERNEL_SHUTDOWN,
        SystemEventType.RUNTIME_READY,
        SystemEventType.RUNTIME_PAUSED,
        SystemEventType.RUNTIME_RESUMED,
        SystemEventType.SNAPSHOT_CREATED,
        SystemEventType.SNAPSHOT_UPDATED,
        SystemEventType.RUNNING_EVENT_CHANGED,
        SystemEventType.RUNNING_CONTEXT_CHANGED,
        SystemEventType.SERVICE_REGISTERED,
        SystemEventType.SERVICE_REMOVED,
    }
)

#: Scheduler vocabulary (Milestone 4): the single recalculation trigger the
#: Scheduler subscribes to; runtime signals are translated into it by the
#: infrastructure RecalculationBridge (approved refinement 1).
SCHEDULER_EVENTS: frozenset[SystemEventType] = frozenset(
    {SystemEventType.SCHEDULER_RECALCULATION_REQUESTED}
)

#: Declared vocabulary whose publishers arrive with later milestones.
RESERVED_EVENTS: frozenset[SystemEventType] = frozenset(
    set(SystemEventType) - KERNEL_EVENTS - SCHEDULER_EVENTS
)


@dataclass(frozen=True)
class SystemEvent:
    """One immutable broadcast on the System Event Bus."""

    event_type: SystemEventType
    occurred_at: datetime
    payload: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))
