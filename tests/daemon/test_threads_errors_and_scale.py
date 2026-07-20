"""Background operation, pause/resume, graceful shutdown, errors, scale."""

import time

import pytest

from paios.daemon.config import DaemonConfig
from paios.daemon.daemon import RuntimeDaemon
from paios.daemon.exceptions import DaemonStateError
from paios.daemon.lifecycle import DaemonState
from paios.daemon.sleep import NoSleep, RealSleep

from tests.daemon.conftest import FakeApplication, simulated_daemon


def fast_daemon(app) -> RuntimeDaemon:
    return RuntimeDaemon(
        app,
        DaemonConfig(
            tick_interval_seconds=0.005,
            shutdown_timeout_seconds=2.0,
            sleep_strategy=RealSleep(),
        ),
    )


def wait_for(condition, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.005)
    return False


class TestBackgroundOperation:
    def test_start_ticks_continuously_and_stops_gracefully(self, fake_app):
        daemon = fast_daemon(fake_app)
        daemon.start()
        assert daemon.state is DaemonState.RUNNING
        assert wait_for(lambda: daemon.tick_count >= 3)
        daemon.stop()
        assert wait_for(lambda: daemon.state is DaemonState.STOPPED)
        settled = daemon.tick_count
        time.sleep(0.05)
        assert daemon.tick_count == settled  # truly stopped

    def test_pause_halts_ticking_resume_continues(self, fake_app):
        daemon = fast_daemon(fake_app)
        daemon.start()
        assert wait_for(lambda: daemon.tick_count >= 2)
        daemon.pause()
        assert daemon.state is DaemonState.PAUSED
        paused_at = daemon.tick_count
        time.sleep(0.1)
        assert daemon.tick_count <= paused_at + 1  # at most one in-flight
        daemon.resume()
        assert wait_for(lambda: daemon.tick_count > paused_at + 1)
        daemon.stop()

    def test_stop_is_responsive_while_paused(self, fake_app):
        daemon = fast_daemon(fake_app)
        daemon.start()
        assert wait_for(lambda: daemon.tick_count >= 1)
        daemon.pause()
        daemon.stop()
        assert wait_for(lambda: daemon.state is DaemonState.STOPPED)

    def test_background_restart(self, fake_app):
        daemon = fast_daemon(fake_app)
        daemon.start()
        assert wait_for(lambda: daemon.tick_count >= 1)
        daemon.stop()
        assert wait_for(lambda: daemon.state is DaemonState.STOPPED)
        count = daemon.tick_count
        daemon.start()
        assert wait_for(lambda: daemon.tick_count > count)
        daemon.stop()

    def test_double_start_rejected_while_running(self, fake_app):
        daemon = fast_daemon(fake_app)
        daemon.start()
        with pytest.raises(DaemonStateError):
            daemon.start()
        daemon.stop()


class TestErrors:
    def test_foreground_tick_error_finishes_then_raises(self):
        app = FakeApplication(fail_on_tick=3)
        daemon = RuntimeDaemon(app, DaemonConfig(sleep_strategy=NoSleep()))
        with pytest.raises(RuntimeError, match="tick exploded"):
            daemon.run_iterations(10)
        assert daemon.state is DaemonState.STOPPED
        assert app.ticks == 3  # third attempt exploded
        assert daemon.tick_count == 2  # completed ticks only
        assert isinstance(daemon.last_error, RuntimeError)

    def test_background_tick_error_is_captured_not_lost(self):
        app = FakeApplication(fail_on_tick=2)
        daemon = fast_daemon(app)
        daemon.start()
        assert wait_for(lambda: daemon.state is DaemonState.STOPPED)
        assert isinstance(daemon.last_error, RuntimeError)

    def test_restart_clears_last_error(self):
        app = FakeApplication(fail_on_tick=1)
        daemon = RuntimeDaemon(app, DaemonConfig(sleep_strategy=NoSleep()))
        with pytest.raises(RuntimeError):
            daemon.run_iterations(1)
        daemon.run_iterations(2)  # fail_on_tick already consumed
        assert daemon.last_error is None
        assert daemon.tick_count == 2  # the exploded attempt never counted


class TestLongRunningSimulation:
    def test_a_simulated_day_of_minute_ticks(self, manual_app):
        manual_app.start()
        daemon = simulated_daemon(manual_app, interval=60.0)
        start = manual_app.components.clock.now()
        daemon.run_iterations(24 * 60)  # one simulated day
        elapsed = manual_app.components.clock.now() - start
        assert elapsed.total_seconds() == pytest.approx(
            (24 * 60 - 1) * 60.0
        )
        assert daemon.tick_count == 24 * 60
        # System stays coherent: still exactly one pending suggestion.
        assert len(manual_app.active_recommendations()) == 1

    def test_performance_sanity(self, fake_app):
        daemon = RuntimeDaemon(fake_app, DaemonConfig(sleep_strategy=NoSleep()))
        started = time.monotonic()
        daemon.run_iterations(500)
        assert time.monotonic() - started < 5.0
        assert fake_app.ticks == 500
