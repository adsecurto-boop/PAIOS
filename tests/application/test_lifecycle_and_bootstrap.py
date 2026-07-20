"""Application lifecycle (canonical startup/shutdown) and composition."""

from pathlib import Path

import pytest

from paios.application.application import Application
from paios.application.bootstrap import build_components
from paios.application.config import ApplicationConfig
from paios.application.exceptions import (
    ApplicationAlreadyStartedError,
    ApplicationNotStartedError,
)
from paios.runtime.clock import ManualClock, SystemClock
from paios.runtime.lifecycle import KernelState

from tests.application.conftest import T0, USER, seed_rest_scenario


class TestBootstrap:
    def test_build_is_pure_construction(self, tmp_path):
        config = ApplicationConfig(data_dir=tmp_path / "data")
        components = build_components(config)
        assert not (tmp_path / "data").exists()  # no side effects
        assert components.kernel.state is KernelState.CREATED

    def test_injected_manual_clock_is_used_everywhere(self, tmp_path):
        clock = ManualClock(T0)
        components = build_components(
            ApplicationConfig(data_dir=tmp_path / "data", clock=clock)
        )
        assert components.clock is clock
        assert components.kernel.clock is clock

    def test_default_clock_is_system_clock(self, tmp_path):
        components = build_components(
            ApplicationConfig(data_dir=tmp_path / "data")
        )
        assert isinstance(components.clock, SystemClock)

    def test_default_data_dir_is_dot_data(self):
        assert ApplicationConfig().data_dir == ".data"
        assert build_components(
            ApplicationConfig()
        ).repositories.data_dir == Path(".data")

    def test_independent_builds_share_nothing(self, tmp_path):
        config = ApplicationConfig(data_dir=tmp_path / "data")
        first = build_components(config)
        second = build_components(config)
        assert first.kernel is not second.kernel
        assert first.scheduler is not second.scheduler


class TestStartup:
    def test_start_reaches_running_with_all_services(self, started_app):
        status = started_app.status()
        assert status.state is KernelState.RUNNING
        assert set(status.registered_services) == {
            "clock",
            "event_bus",
            "snapshot_manager",
            "invariant_checker",
            "scheduler",
        }
        assert started_app.snapshot() is not None

    def test_start_loads_seeded_aggregates(self, started_app):
        counts = started_app.status().aggregate_counts
        assert counts["contexts"] == 1
        assert counts["resources"] == 1
        assert counts["principles"] == 1

    def test_double_start_rejected(self, started_app):
        with pytest.raises(ApplicationAlreadyStartedError):
            started_app.start()

    def test_operations_before_start_rejected(self, app_builder):
        application = app_builder()
        for operation in (
            application.status,
            application.snapshot,
            application.evaluate,
            application.tick,
        ):
            with pytest.raises(ApplicationNotStartedError):
                operation()
        with pytest.raises(ApplicationNotStartedError):
            _ = application.components


class TestShutdown:
    def test_stop_completes_the_canonical_sequence(self, started_app):
        kernel = started_app.components.kernel
        started_app.stop()
        assert not started_app.started
        assert kernel.state is KernelState.STOPPED
        assert kernel.services.names() == ()
        assert kernel.latest_snapshot is None

    def test_stop_before_start_rejected(self, app_builder):
        with pytest.raises(ApplicationNotStartedError):
            app_builder().stop()

    def test_operations_after_stop_rejected(self, started_app):
        started_app.stop()
        with pytest.raises(ApplicationNotStartedError):
            started_app.status()

    def test_restart_recovers_persisted_reality(self, app_builder):
        first = app_builder(seed=seed_rest_scenario)
        first.start()
        event = first.report_spontaneous_action(
            USER, "health", "Unplanned run"
        )
        first.stop()

        second = app_builder()  # same data dir, fresh composition
        second.start()
        restored = second.components.kernel.runtime_state.events
        assert [str(e.event_id) for e in restored] == [str(event.event_id)]
        assert second.status().state is KernelState.RUNNING
        second.stop()

    def test_startup_is_deterministic_across_runs(self, app_builder):
        application = app_builder(seed=seed_rest_scenario)
        application.start()
        first_counts = dict(application.status().aggregate_counts)
        application.stop()
        application = app_builder()
        application.start()
        assert dict(application.status().aggregate_counts) == first_counts
        application.stop()
