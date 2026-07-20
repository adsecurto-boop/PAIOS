"""Kernel boot sequence: load, restore, validate, snapshot, ready."""

import pytest

from paios.domain.value_objects.identifiers import ContextWindowId, EventId
from paios.runtime.exceptions import BootError, KernelLifecycleError
from paios.runtime.kernel import (
    SERVICE_CLOCK,
    SERVICE_EVENT_BUS,
    SERVICE_INVARIANT_CHECKER,
    SERVICE_SNAPSHOT_MANAGER,
)
from paios.runtime.lifecycle import KernelState
from paios.runtime.runtime_state import (
    EventExecutionContext,
    IdleExecutionContext,
    IdleReason,
)
from paios.runtime.system_events import SystemEventType

from tests.repositories.conftest import (
    build_completed_event,
    build_context,
    build_principle,
    build_user,
)
from tests.runtime.conftest import (
    build_active_window,
    build_started_event,
    record_all_events,
    types_of,
)


class TestBootEmptyStore:
    def test_boot_reaches_ready_with_idle_execution(self, kernel):
        kernel.boot()
        assert kernel.state is KernelState.READY
        context = kernel.runtime_state.execution_context
        assert isinstance(context, IdleExecutionContext)
        assert context.reason is IdleReason.WAITING

    def test_boot_registers_exactly_the_four_services(self, kernel):
        kernel.boot()
        assert set(kernel.services.names()) == {
            SERVICE_CLOCK,
            SERVICE_EVENT_BUS,
            SERVICE_SNAPSHOT_MANAGER,
            SERVICE_INVARIANT_CHECKER,
        }

    def test_boot_creates_first_snapshot(self, kernel):
        kernel.boot()
        snapshot = kernel.latest_snapshot
        assert snapshot is not None
        assert snapshot.running_event is None
        assert snapshot.running_context_window is None

    def test_boot_publishes_expected_events_in_order(self, kernel):
        recorded = record_all_events(kernel.event_bus)
        kernel.boot()
        assert types_of(recorded) == [
            SystemEventType.SERVICE_REGISTERED,
            SystemEventType.SERVICE_REGISTERED,
            SystemEventType.SERVICE_REGISTERED,
            SystemEventType.SERVICE_REGISTERED,
            SystemEventType.SNAPSHOT_CREATED,
            SystemEventType.KERNEL_BOOTED,
            SystemEventType.RUNTIME_READY,
        ]

    def test_boot_twice_rejected(self, kernel):
        kernel.boot()
        with pytest.raises(KernelLifecycleError):
            kernel.boot()


class TestBootWithData:
    def test_boot_restores_aggregates_into_runtime_state(self, factory, kernel):
        factory.users().save(build_user())
        factory.principles().save(build_principle())
        factory.contexts().save(build_context())
        factory.events().save(build_completed_event())
        kernel.boot()
        counts = kernel.runtime_state.aggregate_counts()
        assert counts["users"] == 1
        assert counts["principles"] == 1
        assert counts["contexts"] == 1
        assert counts["events"] == 1

    def test_running_user_event_becomes_execution_context(self, factory, kernel):
        factory.events().save(build_started_event())
        factory.context_windows().save(build_active_window())
        kernel.boot()
        context = kernel.runtime_state.execution_context
        assert isinstance(context, EventExecutionContext)
        assert context.event_id == EventId("evt_run")
        assert context.context_window_id == ContextWindowId("win_run")

    def test_snapshot_resolves_running_event_and_window(self, factory, kernel):
        factory.events().save(build_started_event())
        factory.context_windows().save(build_active_window())
        kernel.boot()
        snapshot = kernel.latest_snapshot
        assert snapshot.running_event.event_id == EventId("evt_run")
        assert snapshot.running_context_window.window_id == ContextWindowId(
            "win_run"
        )

    def test_status_reports_operational_details(self, factory, kernel):
        factory.events().save(build_completed_event())
        kernel.boot()
        status = kernel.status()
        assert status.state is KernelState.READY
        assert status.is_operational
        assert status.booted_at is not None
        assert status.aggregate_counts["events"] == 1
        assert len(status.registered_services) == 4
        assert status.latest_snapshot_at is not None


class TestBootFailures:
    def test_invariant_violation_fails_boot(self, factory, kernel):
        factory.events().save(build_started_event("evt_1", window_id="win_1"))
        factory.events().save(build_started_event("evt_2", window_id="win_2"))
        with pytest.raises(BootError):
            kernel.boot()
        assert kernel.state is KernelState.FAILED
        assert kernel.latest_snapshot is None
        assert kernel.services.names() == ()
        with pytest.raises(KernelLifecycleError):
            kernel.runtime_state

    def test_corrupted_store_fails_boot(self, factory, kernel):
        events_file = factory.data_dir / "events.json"
        events_file.write_text('[{"event_id": broken', encoding="utf-8")
        with pytest.raises(BootError):
            kernel.boot()
        assert kernel.state is KernelState.FAILED

    def test_failed_kernel_cannot_reboot(self, factory, kernel):
        factory.events().save(build_started_event("evt_1", window_id="win_1"))
        factory.events().save(build_started_event("evt_2", window_id="win_2"))
        with pytest.raises(BootError):
            kernel.boot()
        with pytest.raises(KernelLifecycleError):
            kernel.boot()
