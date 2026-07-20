"""Fixtures for the Application layer: manual-clock applications over
seeded temporary stores."""

from datetime import datetime, timedelta

import pytest

from paios.application.application import Application
from paios.application.config import ApplicationConfig
from paios.domain.entities.context import Context
from paios.domain.entities.principle import Principle
from paios.domain.entities.resource import Resource
from paios.domain.enums import PrincipleCategory, ResourceType
from paios.domain.value_objects.identifiers import (
    ContextId,
    PrincipleId,
    ResourceId,
    UserId,
)
from paios.repositories.factory import RepositoryFactory
from paios.runtime.clock import ManualClock

T0 = datetime(2026, 7, 21, 9, 0)
USER = UserId("user_001")


def at(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


def seed_context(factory: RepositoryFactory) -> None:
    factory.contexts().save(
        Context(context_id=ContextId("ctx_001"), name="Office", created_at=T0)
    )


def seed_low_energy(factory: RepositoryFactory) -> None:
    factory.resources().save(
        Resource(
            resource_id=ResourceId("res_energy"),
            user_id=USER,
            type=ResourceType.ENERGY,
            current_value=10.0,
            unit="points",
        )
    )


def seed_health_principle(factory: RepositoryFactory) -> None:
    factory.principles().save(
        Principle(
            principle_id=PrincipleId("prin_health"),
            name="Protect Health",
            description="Prioritize health",
            category=PrincipleCategory.HEALTH,
            created_at=T0,
        )
    )


def seed_rest_scenario(factory: RepositoryFactory) -> None:
    """Context + low Energy + Health Principle: the RestRule fires."""
    seed_context(factory)
    seed_low_energy(factory)
    seed_health_principle(factory)


@pytest.fixture
def app_builder(tmp_path):
    """Builds (but does not start) applications over one shared data dir —
    restart tests need the same store across instances."""

    def build(seed=None, clock=None) -> Application:
        data_dir = tmp_path / "data"
        if seed is not None:
            factory = RepositoryFactory(data_dir)
            factory.initialize()
            seed(factory)
        return Application(
            ApplicationConfig(
                data_dir=data_dir,
                clock=clock if clock is not None else ManualClock(T0),
            )
        )

    return build


@pytest.fixture
def started_app(app_builder):
    application = app_builder(seed=seed_rest_scenario)
    application.start()
    yield application
    if application.started:
        application.stop()
