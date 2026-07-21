"""API test fixtures: a router over a real started application."""

import pytest

from paios.api.routes import ApiRouter
from paios.application.application import Application
from paios.application.config import ApplicationConfig
from paios.repositories.factory import RepositoryFactory
from paios.runtime.clock import ManualClock

from tests.application.conftest import T0, seed_rest_scenario


@pytest.fixture
def api_app(tmp_path):
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
def router(api_app):
    return ApiRouter(api_app)


def materialize_event(router: ApiRouter) -> str:
    """Drive the loop through the API only: tick, accept, return event id."""
    status, body = router.handle("POST", "/tick")
    assert status == 200, body
    status, body = router.handle("GET", "/recommendations")
    assert status == 200 and body["recommendations"], body
    recommendation_id = body["recommendations"][0]["recommendation_id"]
    status, body = router.handle(
        "POST", f"/recommendations/{recommendation_id}/accept"
    )
    assert status == 200, body
    status, body = router.handle("GET", "/events")
    assert status == 200 and body["events"], body
    return body["events"][0]["event_id"]
