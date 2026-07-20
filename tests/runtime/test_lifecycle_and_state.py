"""Kernel lifecycle machine, Execution Context hierarchy, Runtime State."""

import pytest

from paios.domain.value_objects.identifiers import ContextWindowId, EventId
from paios.runtime.exceptions import RuntimeInvariantError
from paios.runtime.lifecycle import (
    KERNEL_STATE_MACHINE,
    OPERATIONAL_STATES,
    KernelState,
)
from paios.runtime.runtime_state import (
    EventExecutionContext,
    IdleExecutionContext,
    IdleReason,
    RuntimeState,
)

from tests.runtime.conftest import T0, at


class TestKernelStateMachine:
    def test_boot_path(self):
        assert KERNEL_STATE_MACHINE.can_transition(
            KernelState.CREATED, KernelState.BOOTING
        )
        assert KERNEL_STATE_MACHINE.can_transition(
            KernelState.BOOTING, KernelState.READY
        )
        assert KERNEL_STATE_MACHINE.can_transition(
            KernelState.BOOTING, KernelState.FAILED
        )

    def test_pause_resume_cycle(self):
        assert KERNEL_STATE_MACHINE.can_transition(
            KernelState.RUNNING, KernelState.PAUSED
        )
        assert KERNEL_STATE_MACHINE.can_transition(
            KernelState.PAUSED, KernelState.RUNNING
        )

    def test_shutdown_from_every_operational_state(self):
        for state in OPERATIONAL_STATES:
            assert KERNEL_STATE_MACHINE.can_transition(
                state, KernelState.STOPPING
            )
        assert KERNEL_STATE_MACHINE.can_transition(
            KernelState.STOPPING, KernelState.STOPPED
        )

    def test_invalid_shortcuts(self):
        assert not KERNEL_STATE_MACHINE.can_transition(
            KernelState.CREATED, KernelState.RUNNING
        )
        assert not KERNEL_STATE_MACHINE.can_transition(
            KernelState.STOPPED, KernelState.BOOTING
        )
        assert KERNEL_STATE_MACHINE.is_terminal(KernelState.STOPPED)
        assert KERNEL_STATE_MACHINE.is_terminal(KernelState.FAILED)


class TestExecutionContexts:
    def test_idle_context_owns_no_context_window(self):
        idle = IdleExecutionContext(since=T0, reason=IdleReason.BOOTING)
        assert not hasattr(idle, "context_window_id")

    def test_event_context_owns_event_and_window(self):
        context = EventExecutionContext(
            since=T0,
            event_id=EventId("evt_run"),
            context_window_id=ContextWindowId("win_run"),
        )
        assert context.event_id == EventId("evt_run")
        assert context.context_window_id == ContextWindowId("win_run")

    def test_event_context_requires_both_references(self):
        with pytest.raises(RuntimeInvariantError):
            EventExecutionContext(since=T0, event_id=EventId("evt_run"))
        with pytest.raises(RuntimeInvariantError):
            EventExecutionContext(
                since=T0, context_window_id=ContextWindowId("win_run")
            )


class TestRuntimeState:
    def make_state(self) -> RuntimeState:
        return RuntimeState(
            current_time=T0,
            execution_context=IdleExecutionContext(since=T0),
        )

    def test_exactly_one_execution_context_always(self):
        with pytest.raises(RuntimeInvariantError):
            RuntimeState(current_time=T0, execution_context=None)
        state = self.make_state()
        with pytest.raises(RuntimeInvariantError):
            state.replace_execution_context(None)

    def test_replace_returns_previous_context(self):
        state = self.make_state()
        previous = state.execution_context
        new_context = EventExecutionContext(
            since=at(5),
            event_id=EventId("evt_run"),
            context_window_id=ContextWindowId("win_run"),
        )
        returned = state.replace_execution_context(new_context)
        assert returned is previous
        assert state.execution_context is new_context

    def test_only_event_context_yields_running_window(self):
        state = self.make_state()
        assert state.running_context_window_id is None
        state.replace_execution_context(
            EventExecutionContext(
                since=at(5),
                event_id=EventId("evt_run"),
                context_window_id=ContextWindowId("win_run"),
            )
        )
        assert state.running_context_window_id == ContextWindowId("win_run")
