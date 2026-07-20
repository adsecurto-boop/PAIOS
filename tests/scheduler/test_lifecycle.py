"""Scheduler state machine (STATE_MACHINES.md section 4) and cycle states."""

import pytest

from paios.domain.errors import InvalidTransitionError
from paios.scheduler.lifecycle import SCHEDULER_STATE_MACHINE, SchedulerState

from tests.scheduler.conftest import seed_context, seed_running_event


class TestSchedulerStateMachine:
    def test_full_planning_path(self):
        path = [
            SchedulerState.IDLE,
            SchedulerState.OBSERVING,
            SchedulerState.EVALUATING,
            SchedulerState.PLANNING,
            SchedulerState.SCHEDULING,
            SchedulerState.MONITORING,
        ]
        for source, target in zip(path, path[1:]):
            assert SCHEDULER_STATE_MACHINE.can_transition(source, target)

    def test_recalculation_loop(self):
        assert SCHEDULER_STATE_MACHINE.can_transition(
            SchedulerState.MONITORING, SchedulerState.RECALCULATING
        )
        assert SCHEDULER_STATE_MACHINE.can_transition(
            SchedulerState.RECALCULATING, SchedulerState.SCHEDULING
        )

    def test_horizon_end_returns_to_idle(self):
        assert SCHEDULER_STATE_MACHINE.can_transition(
            SchedulerState.MONITORING, SchedulerState.IDLE
        )

    def test_documented_invalid_bypasses(self):
        with pytest.raises(InvalidTransitionError):
            SCHEDULER_STATE_MACHINE.validate(
                SchedulerState.OBSERVING, SchedulerState.SCHEDULING
            )
        with pytest.raises(InvalidTransitionError):
            SCHEDULER_STATE_MACHINE.validate(
                SchedulerState.IDLE, SchedulerState.PLANNING
            )
        with pytest.raises(InvalidTransitionError):
            SCHEDULER_STATE_MACHINE.validate(
                SchedulerState.RECALCULATING, SchedulerState.MONITORING
            )


class TestSchedulerRuntimeStates:
    def test_empty_system_settles_idle(self, system):
        wired = system(seed=seed_context)
        assert wired.scheduler.state is SchedulerState.IDLE
        assert wired.scheduler.plan.is_empty

    def test_running_event_keeps_monitoring(self, system):
        def seed(factory):
            seed_context(factory)
            seed_running_event(factory)

        wired = system(seed=seed)
        assert wired.scheduler.state is SchedulerState.MONITORING

    def test_double_attach_rejected(self, system):
        from paios.scheduler.exceptions import SchedulerLifecycleError

        wired = system(seed=seed_context)
        with pytest.raises(SchedulerLifecycleError):
            wired.scheduler.attach()
