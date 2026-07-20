"""Fixtures for Scheduler tests: a fully wired system (repositories,
kernel, bridge, persistence sync, scheduler) over a manual clock."""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from paios.domain.entities.event_disturber import EventDisturber
from paios.domain.entities.recommendation import Recommendation
from paios.domain.enums import DisturberSeverity, DisturberType
from paios.domain.value_objects.identifiers import (
    ContextWindowId,
    EventDisturberId,
    RecommendationId,
    UserId,
)
from paios.infrastructure.persistence_sync import PersistenceSync
from paios.infrastructure.recalculation_bridge import RecalculationBridge
from paios.repositories.factory import RepositoryFactory
from paios.runtime.clock import ManualClock
from paios.runtime.kernel import RuntimeKernel
from paios.runtime.system_events import SystemEvent, SystemEventType
from paios.scheduler.scheduler import Scheduler

from tests.repositories.conftest import build_context
from tests.runtime.conftest import build_active_window, build_started_event

T0 = datetime(2026, 7, 20, 9, 0)


def at(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


def build_pending_recommendation(
    recommendation_id: str = "rec_001",
    priority: float = 5.0,
    created_at: datetime | None = None,
    expires_at: datetime | None = None,
    presented_at: datetime | None = None,
    suggested_timing: datetime | None = None,
) -> Recommendation:
    created = created_at or T0
    recommendation = Recommendation(
        recommendation_id=RecommendationId(recommendation_id),
        user_id=UserId("user_001"),
        reason="Study ISTQB Chapter 5",
        created_at=created,
        expires_at=expires_at or (created + timedelta(minutes=120)),
        priority=priority,
        expected_benefit="Chapter 5 mastery",
        suggested_timing=suggested_timing,
    )
    recommendation.present(presented_at or (created + timedelta(minutes=1)))
    return recommendation


def build_applied_disturber(
    disturber_id: str = "dist_001", window_id: str = "win_run"
) -> EventDisturber:
    disturber = EventDisturber(
        event_disturber_id=EventDisturberId(disturber_id),
        user_id=UserId("user_001"),
        type=DisturberType.WORK,
        description="Team Lead requested overtime",
        severity=DisturberSeverity.HIGH,
        occurred_at=T0,
    )
    disturber.record(at(1))
    disturber.analyze(at(2))
    disturber.apply(at(3), ContextWindowId(window_id))
    return disturber


def seed_context(factory: RepositoryFactory) -> None:
    factory.contexts().save(build_context())


def seed_running_event(factory: RepositoryFactory) -> None:
    factory.events().save(build_started_event())
    factory.context_windows().save(build_active_window())


def publish_time(kernel: RuntimeKernel, moment: datetime) -> None:
    kernel.event_bus.publish(
        SystemEvent(SystemEventType.TIME_PROGRESSED, moment, {})
    )


def publish_disturbance(
    kernel: RuntimeKernel, moment: datetime, disturber_id: str | None = None
) -> None:
    payload = {}
    if disturber_id is not None:
        payload["event_disturber_id"] = disturber_id
    kernel.event_bus.publish(
        SystemEvent(SystemEventType.DISTURBANCE_DETECTED, moment, payload)
    )


@pytest.fixture
def system(tmp_path):
    """Builder for a fully wired system; multiple builds share the same
    data directory, which is exactly what crash-recovery tests need."""

    def build(seed=None, planner=None, start_kernel=True):
        factory = RepositoryFactory(tmp_path / "data")
        factory.initialize()
        if seed is not None:
            seed(factory)
        clock = ManualClock(T0)
        kernel = RuntimeKernel(repositories=factory, clock=clock)
        kernel.boot()
        if start_kernel:
            kernel.start()
        bridge = RecalculationBridge(kernel)
        bridge.attach()
        sync = PersistenceSync(kernel, factory)
        sync.attach()
        scheduler = Scheduler(kernel, planner=planner)
        scheduler.attach()
        return SimpleNamespace(
            factory=factory,
            clock=clock,
            kernel=kernel,
            scheduler=scheduler,
            bridge=bridge,
            sync=sync,
        )

    return build
