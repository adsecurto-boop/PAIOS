"""PAIOS Scheduler (Milestone 4).

The sole owner of the future and the sole controller of Event state
transitions (ADR-002; BUSINESS_RULES.md - Scheduler Rules). Event-driven:
it subscribes to exactly one bus topic — SchedulerRecalculationRequested —
and reacts deterministically to every trigger (approved rulings G9/G11).

The Scheduler orchestrates; the Planner computes plans (refinement 3). It
never reasons, never learns, never persists, never edits History, and
requests all runtime effects (Context Window transitions, Execution
Context swaps, aggregate admission) from the Runtime Kernel (G6).
"""

from paios.scheduler.exceptions import (
    SchedulerError,
    SchedulerLifecycleError,
    SchedulingConflictError,
    UnknownWorkError,
)
from paios.scheduler.lifecycle import SCHEDULER_STATE_MACHINE, SchedulerState
from paios.scheduler.plan import PlanEntry, SchedulingPlan
from paios.scheduler.planner import (
    DEFAULT_SLOT_MINUTES,
    DeterministicPlanner,
    PlanCandidate,
    Planner,
)
from paios.scheduler.scheduler import RecalculationReason, Scheduler

__all__ = [
    "DEFAULT_SLOT_MINUTES",
    "DeterministicPlanner",
    "PlanCandidate",
    "PlanEntry",
    "Planner",
    "RecalculationReason",
    "SCHEDULER_STATE_MACHINE",
    "Scheduler",
    "SchedulerError",
    "SchedulerLifecycleError",
    "SchedulerState",
    "SchedulingConflictError",
    "SchedulingPlan",
    "UnknownWorkError",
]
