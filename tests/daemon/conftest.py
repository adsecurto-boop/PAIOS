"""Daemon fixtures: real applications on manual clocks, plus a fake app."""

from types import SimpleNamespace

import pytest

from paios.application.application import Application
from paios.application.config import ApplicationConfig
from paios.daemon.config import DaemonConfig
from paios.daemon.daemon import RuntimeDaemon
from paios.daemon.sleep import NoSleep, SimulatedSleep
from paios.repositories.factory import RepositoryFactory
from paios.runtime.clock import ManualClock

from tests.application.conftest import T0, seed_rest_scenario


@pytest.fixture
def manual_app(tmp_path):
    """A real Application over a ManualClock and seeded store."""
    data_dir = tmp_path / "data"
    factory = RepositoryFactory(data_dir)
    factory.initialize()
    seed_rest_scenario(factory)
    application = Application(
        ApplicationConfig(data_dir=data_dir, clock=ManualClock(T0))
    )
    yield application
    if application.started:
        application.stop()


@pytest.fixture
def daemon(manual_app):
    """Deterministic daemon: manual clock + NoSleep + 60s interval."""
    return RuntimeDaemon(
        manual_app,
        DaemonConfig(tick_interval_seconds=60.0, sleep_strategy=NoSleep()),
    )


class FakeApplication:
    """Duck-typed Application recording ticks; optionally failing."""

    def __init__(self, clock=None, fail_on_tick: int | None = None):
        self.clock = clock if clock is not None else ManualClock(T0)
        self.components = SimpleNamespace(clock=self.clock)
        self.started = False
        self.ticks = 0
        self.start_calls = 0
        self._fail_on = fail_on_tick

    def start(self):
        self.started = True
        self.start_calls += 1

    def stop(self):
        self.started = False

    def tick(self):
        self.ticks += 1
        if self._fail_on is not None and self.ticks == self._fail_on:
            raise RuntimeError("tick exploded")
        return SimpleNamespace(no_action=True, recommendations=())


@pytest.fixture
def fake_app():
    return FakeApplication()


def simulated_daemon(app, interval: float = 60.0, **config) -> RuntimeDaemon:
    """Daemon whose sleeps advance the app's manual clock — deterministic
    long-running time flow."""
    return RuntimeDaemon(
        app,
        DaemonConfig(
            tick_interval_seconds=interval,
            sleep_strategy=SimulatedSleep(app.components.clock),
            **config,
        ),
    )
