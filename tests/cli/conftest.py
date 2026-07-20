"""CLI test fixtures: a real started application and a recording fake."""

from types import SimpleNamespace

import pytest

from paios.application.application import Application
from paios.application.config import ApplicationConfig
from paios.cli.commands import CommandProcessor
from paios.repositories.factory import RepositoryFactory
from paios.runtime.clock import ManualClock

from tests.application.conftest import T0, seed_rest_scenario


@pytest.fixture
def cli_app(tmp_path):
    data_dir = tmp_path / "data"
    factory = RepositoryFactory(data_dir)
    factory.initialize()
    seed_rest_scenario(factory)
    application = Application(
        ApplicationConfig(data_dir=data_dir, clock=ManualClock(T0))
    )
    application.start()
    yield application
    if application.started:
        application.stop()


@pytest.fixture
def processor(cli_app):
    return CommandProcessor(cli_app)


class RecordingApplication:
    """Duck-typed Application fake: records every delegation."""

    def __init__(self):
        self.calls: list[tuple] = []
        self._recommendation = SimpleNamespace(
            recommendation_id="rec_stub",
            status=SimpleNamespace(value="Pending"),
            reason="Stub recommendation",
            priority=1.0,
            confidence_score=0.5,
            expires_at=None,
        )

    def _record(self, name, *args, **kwargs):
        self.calls.append((name, args, kwargs))

    def start(self):
        self._record("start")

    def stop(self):
        self._record("stop")

    def active_recommendations(self):
        self._record("active_recommendations")
        return (self._recommendation,)

    def snapshot(self):
        self._record("snapshot")
        return None

    def accept_recommendation(self, rec_id, at=None):
        self._record("accept_recommendation", rec_id)

    def reject_recommendation(self, rec_id, at=None, reason=None):
        self._record("reject_recommendation", rec_id)

    def start_event(self, event_id, at=None):
        self._record("start_event", event_id)

    def pause_event(self, event_id, at=None):
        self._record("pause_event", event_id)

    def resume_event(self, event_id, at=None):
        self._record("resume_event", event_id)

    def complete_event(self, event_id, at=None, outcome=None, actual_outcome=None):
        self._record("complete_event", event_id, actual_outcome)

    def cancel_event(self, event_id, at=None, reason=None):
        self._record("cancel_event", event_id)

    def called(self, name):
        return [call for call in self.calls if call[0] == name]


@pytest.fixture
def recording():
    fake = RecordingApplication()
    return fake, CommandProcessor(fake)
