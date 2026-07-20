"""Daemon lifecycle transitions and clock-advancing helpers."""

from datetime import timedelta

import pytest

from paios.daemon.daemon import RuntimeDaemon
from paios.daemon.exceptions import ClockAdvanceError, DaemonStateError
from paios.daemon.lifecycle import DaemonState, validate_transition

from tests.application.conftest import T0, at
from tests.daemon.conftest import FakeApplication


class TestLifecycleMachine:
    def test_valid_paths(self):
        validate_transition(DaemonState.CREATED, DaemonState.RUNNING)
        validate_transition(DaemonState.RUNNING, DaemonState.PAUSED)
        validate_transition(DaemonState.PAUSED, DaemonState.RUNNING)
        validate_transition(DaemonState.RUNNING, DaemonState.STOPPING)
        validate_transition(DaemonState.STOPPING, DaemonState.STOPPED)
        validate_transition(DaemonState.STOPPED, DaemonState.RUNNING)  # restart

    def test_invalid_paths(self):
        with pytest.raises(DaemonStateError):
            validate_transition(DaemonState.CREATED, DaemonState.PAUSED)
        with pytest.raises(DaemonStateError):
            validate_transition(DaemonState.CREATED, DaemonState.STOPPED)
        with pytest.raises(DaemonStateError):
            validate_transition(DaemonState.STOPPED, DaemonState.PAUSED)


class TestLifecycleOperations:
    def test_created_daemon_cannot_pause_resume_or_stop(self, daemon):
        with pytest.raises(DaemonStateError):
            daemon.pause()
        with pytest.raises(DaemonStateError):
            daemon.resume()
        with pytest.raises(DaemonStateError):
            daemon.stop()

    def test_run_iterations_finishes_stopped(self, daemon):
        daemon.run_iterations(2)
        assert daemon.state is DaemonState.STOPPED
        assert daemon.tick_count == 2

    def test_restart_after_stop(self, daemon):
        daemon.run_iterations(1)
        daemon.run_iterations(2)  # Stopped -> Running again
        assert daemon.tick_count == 3
        assert daemon.state is DaemonState.STOPPED

    def test_tick_once_requires_not_paused(self, fake_app):
        daemon = RuntimeDaemon(fake_app)
        daemon._begin()
        daemon.pause()
        with pytest.raises(DaemonStateError):
            daemon.tick_once()
        daemon.resume()
        daemon.tick_once()
        assert fake_app.ticks == 1


class TestClockHelpers:
    def test_advance_minutes_and_seconds(self, daemon, manual_app):
        daemon.advance(minutes=5, seconds=30)
        assert manual_app.components.clock.now() == T0 + timedelta(
            minutes=5, seconds=30
        )

    def test_advance_to(self, daemon, manual_app):
        daemon.advance_to(at(90))
        assert manual_app.components.clock.now() == at(90)

    def test_advance_to_backwards_rejected(self, daemon):
        daemon.advance(minutes=10)
        with pytest.raises(ClockAdvanceError, match="monotonically"):
            daemon.advance_to(T0)

    def test_system_clock_cannot_be_advanced(self, tmp_path):
        from paios.application.application import Application
        from paios.application.config import ApplicationConfig

        application = Application(
            ApplicationConfig(data_dir=tmp_path / "data")
        )  # defaults to SystemClock
        daemon = RuntimeDaemon(application)
        try:
            with pytest.raises(ClockAdvanceError):
                daemon.advance(minutes=1)
            with pytest.raises(ClockAdvanceError):
                daemon.advance_to(T0)
        finally:
            application.stop()

    def test_advance_auto_starts_the_application(self, daemon, manual_app):
        assert not manual_app.started
        daemon.advance(minutes=1)
        assert manual_app.started
