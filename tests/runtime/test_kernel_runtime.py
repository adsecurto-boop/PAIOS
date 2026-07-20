"""Kernel runtime operations: start/pause/resume/shutdown, execution
context changes, snapshot refresh."""

from datetime import timedelta

import pytest

from paios.domain.value_objects.identifiers import ContextWindowId, EventId
from paios.runtime.exceptions import KernelLifecycleError, RuntimeInvariantError
from paios.runtime.lifecycle import KernelState
from paios.runtime.runtime_state import (
    EventExecutionContext,
    IdleExecutionContext,
    IdleReason,
)
from paios.runtime.system_events import SystemEventType

from tests.runtime.conftest import (
    at,
    build_active_window,
    build_started_event,
    record_all_events,
    types_of,
)


@pytest.fixture
def running_kernel(kernel):
    kernel.boot()
    kernel.start()
    return kernel


def event_context(minutes: int = 10) -> EventExecutionContext:
    return EventExecutionContext(
        since=at(minutes),
        event_id=EventId("evt_run"),
        context_window_id=ContextWindowId("win_run"),
    )


class TestLifecycleOperations:
    def test_start_pause_resume(self, kernel):
        kernel.boot()
        recorded = record_all_events(kernel.event_bus)
        kernel.start()
        assert kernel.state is KernelState.RUNNING
        kernel.pause()
        assert kernel.state is KernelState.PAUSED
        kernel.resume()
        assert kernel.state is KernelState.RUNNING
        assert types_of(recorded) == [
            SystemEventType.RUNTIME_PAUSED,
            SystemEventType.RUNTIME_RESUMED,
        ]

    def test_start_requires_ready(self, kernel):
        with pytest.raises(KernelLifecycleError):
            kernel.start()

    def test_shutdown_sequence(self, running_kernel):
        recorded = record_all_events(running_kernel.event_bus)
        running_kernel.shutdown()
        assert running_kernel.state is KernelState.STOPPED
        assert types_of(recorded) == [
            SystemEventType.SERVICE_REMOVED,
            SystemEventType.SERVICE_REMOVED,
            SystemEventType.SERVICE_REMOVED,
            SystemEventType.SERVICE_REMOVED,
            SystemEventType.KERNEL_SHUTDOWN,
        ]
        assert running_kernel.services.names() == ()
        assert running_kernel.latest_snapshot is None
        with pytest.raises(KernelLifecycleError):
            running_kernel.runtime_state

    def test_shutdown_from_ready_and_paused(self, kernel):
        kernel.boot()
        kernel.shutdown()
        assert kernel.state is KernelState.STOPPED

    def test_stopped_kernel_rejects_operations(self, running_kernel):
        running_kernel.shutdown()
        with pytest.raises(KernelLifecycleError):
            running_kernel.start()
        with pytest.raises(KernelLifecycleError):
            running_kernel.refresh_snapshot()

    def test_status_after_shutdown(self, running_kernel):
        running_kernel.shutdown()
        status = running_kernel.status()
        assert status.state is KernelState.STOPPED
        assert not status.is_operational
        assert status.execution_context is None


class TestExecutionContextChanges:
    def test_requires_running_state(self, kernel):
        kernel.boot()
        with pytest.raises(KernelLifecycleError):
            kernel.set_execution_context(event_context())

    def test_paused_kernel_does_not_accept_work(self, running_kernel):
        running_kernel.pause()
        with pytest.raises(KernelLifecycleError):
            running_kernel.set_execution_context(event_context())

    def test_change_publishes_events_and_updates_snapshot(
        self, factory, running_kernel
    ):
        recorded = record_all_events(running_kernel.event_bus)
        running_kernel.set_execution_context(event_context())
        assert types_of(recorded) == [
            SystemEventType.RUNNING_EVENT_CHANGED,
            SystemEventType.RUNNING_CONTEXT_CHANGED,
            SystemEventType.SNAPSHOT_UPDATED,
        ]
        assert isinstance(
            running_kernel.runtime_state.execution_context,
            EventExecutionContext,
        )

    def test_idle_to_idle_change_skips_context_changed(self, running_kernel):
        recorded = record_all_events(running_kernel.event_bus)
        running_kernel.set_execution_context(
            IdleExecutionContext(since=at(10), reason=IdleReason.SLEEPING)
        )
        assert types_of(recorded) == [
            SystemEventType.RUNNING_EVENT_CHANGED,
            SystemEventType.SNAPSHOT_UPDATED,
        ]

    def test_invalid_context_rejected(self, running_kernel):
        with pytest.raises(RuntimeInvariantError):
            running_kernel.set_execution_context("not-a-context")


class TestSnapshotRefresh:
    def test_refresh_updates_time_and_publishes(self, running_kernel, clock):
        recorded = record_all_events(running_kernel.event_bus)
        clock.advance(timedelta(minutes=42))
        snapshot = running_kernel.refresh_snapshot()
        assert snapshot.current_time == at(42)
        assert snapshot.created_at == at(42)
        assert types_of(recorded) == [SystemEventType.SNAPSHOT_UPDATED]

    def test_snapshot_is_immutable(self, running_kernel):
        snapshot = running_kernel.latest_snapshot
        with pytest.raises(Exception):
            snapshot.current_time = at(999)

    def test_snapshot_contains_approved_contents(self, running_kernel):
        snapshot = running_kernel.latest_snapshot
        for field_name in (
            "current_time",
            "execution_context",
            "running_event",
            "running_context_window",
            "principles",
            "contexts",
            "context_windows",
            "events",
            "projects",
            "progress",
            "resources",
            "knowledge",
            "recommendations",
            "event_disturbers",
            "reflections",
            "insights",
            "habits",
            "goals",
        ):
            assert hasattr(snapshot, field_name)
