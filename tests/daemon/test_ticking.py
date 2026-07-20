"""Ticking semantics: delegation, determinism, drift-free scheduling."""

from datetime import timedelta

import pytest

from paios.daemon.config import DaemonConfig
from paios.daemon.daemon import RuntimeDaemon
from paios.daemon.sleep import NoSleep

from tests.application.conftest import T0
from tests.daemon.conftest import FakeApplication, simulated_daemon


class TestDelegation:
    def test_tick_once_delegates_exactly_once(self, fake_app):
        daemon = RuntimeDaemon(fake_app, DaemonConfig(sleep_strategy=NoSleep()))
        result = daemon.tick_once()
        assert fake_app.ticks == 1
        assert result.no_action
        assert daemon.last_result is result
        assert daemon.last_tick_at == fake_app.clock.now()

    def test_daemon_auto_starts_the_application(self, fake_app):
        daemon = RuntimeDaemon(fake_app, DaemonConfig(sleep_strategy=NoSleep()))
        daemon.tick_once()
        assert fake_app.started
        assert fake_app.start_calls == 1

    def test_run_iterations_ticks_exactly_n_times(self, fake_app):
        daemon = RuntimeDaemon(fake_app, DaemonConfig(sleep_strategy=NoSleep()))
        daemon.run_iterations(5)
        assert fake_app.ticks == 5
        assert daemon.tick_count == 5

    def test_run_until_predicate(self, fake_app):
        daemon = RuntimeDaemon(fake_app, DaemonConfig(sleep_strategy=NoSleep()))
        daemon.run_until(lambda d: d.tick_count >= 3)
        assert daemon.tick_count == 3

    def test_startup_delay_is_slept_first(self, fake_app):
        sleep = NoSleep()
        daemon = RuntimeDaemon(
            fake_app,
            DaemonConfig(startup_delay_seconds=2.5, sleep_strategy=sleep),
        )
        daemon.run_iterations(1)
        assert sleep.calls[0] == 2.5


class TestDeterministicLooping:
    def test_identical_systems_tick_identically(self, tmp_path):
        from paios.application.application import Application
        from paios.application.config import ApplicationConfig
        from paios.repositories.factory import RepositoryFactory
        from paios.runtime.clock import ManualClock
        from tests.application.conftest import seed_rest_scenario

        def build(name):
            data_dir = tmp_path / name
            factory = RepositoryFactory(data_dir)
            factory.initialize()
            seed_rest_scenario(factory)
            application = Application(
                ApplicationConfig(data_dir=data_dir, clock=ManualClock(T0))
            )
            return application, simulated_daemon_over(application)

        def simulated_daemon_over(application):
            application.start()
            return simulated_daemon(application, interval=60.0)

        app_a, daemon_a = build("a")
        app_b, daemon_b = build("b")
        daemon_a.run_iterations(3)
        daemon_b.run_iterations(3)
        ids_a = {str(r.recommendation_id) for r in app_a.active_recommendations()}
        ids_b = {str(r.recommendation_id) for r in app_b.active_recommendations()}
        assert ids_a == ids_b
        app_a.stop()
        app_b.stop()

    def test_repeated_ticking_is_stable_no_duplicates(self, manual_app):
        manual_app.start()
        daemon = simulated_daemon(manual_app, interval=60.0)
        daemon.run_iterations(5)
        # The rest recommendation is produced once and stays pending;
        # later ticks deduplicate through the Decision Engine.
        assert len(manual_app.active_recommendations()) == 1


class TestDriftFreeScheduling:
    def test_sleeps_are_exactly_the_interval(self, manual_app):
        manual_app.start()
        daemon = simulated_daemon(manual_app, interval=60.0)
        daemon.run_iterations(5)
        sleep = daemon._sleep
        assert len(sleep.calls) == 4  # no sleep after the final tick
        assert all(call == pytest.approx(60.0) for call in sleep.calls)

    def test_tick_times_are_exactly_interval_spaced(self, manual_app):
        manual_app.start()
        daemon = simulated_daemon(manual_app, interval=60.0)
        moments = []
        daemon.run_until(
            lambda d: (moments.append(d.last_tick_at), len(moments) >= 4)[1]
        )
        gaps = {
            (later - earlier)
            for earlier, later in zip(moments, moments[1:])
        }
        assert gaps == {timedelta(seconds=60)}

    def test_behind_schedule_catches_up_without_negative_sleep(self):
        class SlowTickApp(FakeApplication):
            def tick(self):
                self.clock.advance(timedelta(seconds=90))  # tick > interval
                return super().tick()

        app = SlowTickApp()
        daemon = RuntimeDaemon(
            app,
            DaemonConfig(tick_interval_seconds=60.0, sleep_strategy=NoSleep()),
        )
        daemon.run_iterations(3)
        assert app.ticks == 3
        assert all(call >= 0 for call in daemon._sleep.calls)
