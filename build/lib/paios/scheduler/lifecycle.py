"""Scheduler state machine — STATE_MACHINES.md section 4, edge-for-edge.

The historical CALCULATING/DISTURBED machine in STATE_MACHINE_DESIGN.md is
superseded and not implemented. The Scheduler is a runtime component, not
History: it validates every move against this machine but does not keep an
unbounded evidence trail of its own housekeeping states.
"""

from enum import Enum, unique

from paios.domain.state_machines.machine import StateMachine


@unique
class SchedulerState(Enum):
    IDLE = "Idle"
    OBSERVING = "Observing"
    EVALUATING = "Evaluating"
    PLANNING = "Planning"
    SCHEDULING = "Scheduling"
    MONITORING = "Monitoring"
    RECALCULATING = "Recalculating"


SCHEDULER_STATE_MACHINE: StateMachine[SchedulerState] = StateMachine(
    "Scheduler Lifecycle",
    {
        SchedulerState.IDLE: frozenset({SchedulerState.OBSERVING}),
        SchedulerState.OBSERVING: frozenset({SchedulerState.EVALUATING}),
        SchedulerState.EVALUATING: frozenset({SchedulerState.PLANNING}),
        SchedulerState.PLANNING: frozenset({SchedulerState.SCHEDULING}),
        SchedulerState.SCHEDULING: frozenset({SchedulerState.MONITORING}),
        SchedulerState.MONITORING: frozenset(
            {SchedulerState.RECALCULATING, SchedulerState.IDLE}
        ),
        SchedulerState.RECALCULATING: frozenset({SchedulerState.SCHEDULING}),
    },
)
