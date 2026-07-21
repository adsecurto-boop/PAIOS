"""Dashboard test fixtures: a real started application plus a strict
read-only recording fake that fails on ANY non-query facade access."""

from datetime import datetime
from types import SimpleNamespace

import pytest

from paios.application.application import Application
from paios.application.config import ApplicationConfig
from paios.repositories.factory import RepositoryFactory
from paios.runtime.clock import ManualClock

from tests.application.conftest import T0, seed_rest_scenario

#: The complete read-only facade surface the dashboard may touch.
ALLOWED_QUERIES = frozenset(
    {
        "current_time",
        "status",
        "snapshot",
        "scheduler_state",
        "active_recommendations",
        "active_event_disturbers",
        "list_events",
        "list_goals",
        "list_projects",
        "get_project_progress",
        "list_resources",
        "list_habits",
        "list_insights",
        "list_reflections",
        "list_knowledge",
    }
)


@pytest.fixture
def dash_app(tmp_path):
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


class ReadOnlyRecordingApplication:
    """Answers every allowed query with empty/stub data and records the
    call; any other attribute access raises — proof the dashboard is
    read-only and facade-only."""

    def __init__(self):
        self.calls: list[str] = []
        self._status = SimpleNamespace(
            state=SimpleNamespace(value="Running"),
            is_operational=True,
            latest_snapshot_at=datetime(2026, 7, 21, 9, 0),
        )

    def __getattr__(self, name):
        if name not in ALLOWED_QUERIES:
            raise AssertionError(
                f"Dashboard touched non-query facade member {name!r}"
            )
        def _query(*args, **kwargs):
            self.calls.append(name)
            if name == "current_time":
                return datetime(2026, 7, 21, 9, 0)
            if name == "status":
                return self._status
            if name == "scheduler_state":
                return SimpleNamespace(value="Idle")
            if name == "snapshot":
                return None
            if name == "get_project_progress":
                return None
            if name in ("active_recommendations", "active_event_disturbers"):
                return ()
            return []
        return _query


@pytest.fixture
def recording_app():
    return ReadOnlyRecordingApplication()
