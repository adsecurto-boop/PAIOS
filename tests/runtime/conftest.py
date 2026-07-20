"""Fixtures for Runtime Kernel tests: manual clock, seeded repositories.

Domain object builders are reused from the repository test suite; runtime
adds builders for running (Started) Events and Active Context Windows.
"""

from datetime import datetime, timedelta

import pytest

from paios.domain.entities.context_window import ContextWindow
from paios.domain.entities.event import Event
from paios.domain.enums import EventStatus
from paios.domain.value_objects.identifiers import (
    ContextId,
    ContextWindowId,
    EventId,
    UserId,
)
from paios.repositories.factory import RepositoryFactory
from paios.runtime.clock import ManualClock
from paios.runtime.event_bus import EventBus
from paios.runtime.kernel import RuntimeKernel
from paios.runtime.system_events import SystemEvent, SystemEventType

T0 = datetime(2026, 7, 20, 9, 0)


def at(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


def build_started_event(
    event_id: str = "evt_run",
    user_id: str = "user_001",
    window_id: str = "win_run",
) -> Event:
    event = Event(
        event_id=EventId(event_id),
        user_id=UserId(user_id),
        context_window_id=ContextWindowId(window_id),
        category="study",
        description="Studying ISTQB Chapter 4",
    )
    event.transition_to(EventStatus.SCHEDULED, at(1))
    event.transition_to(EventStatus.READY, at(2))
    event.transition_to(EventStatus.STARTED, at(3))
    return event


def build_active_window(
    window_id: str = "win_run", event_id: str = "evt_run"
) -> ContextWindow:
    window = ContextWindow(
        window_id=ContextWindowId(window_id),
        context_id=ContextId("ctx_001"),
        event_id=EventId(event_id),
    )
    window.activate(at(3), reason_started="Study session began")
    return window


@pytest.fixture
def clock() -> ManualClock:
    return ManualClock(T0)


@pytest.fixture
def factory(tmp_path) -> RepositoryFactory:
    repository_factory = RepositoryFactory(tmp_path / "data")
    repository_factory.initialize()
    return repository_factory


@pytest.fixture
def kernel(factory, clock) -> RuntimeKernel:
    return RuntimeKernel(repositories=factory, clock=clock)


def record_all_events(bus: EventBus) -> list[SystemEvent]:
    """Subscribe to every SystemEventType and record published events."""
    recorded: list[SystemEvent] = []
    for event_type in SystemEventType:
        bus.subscribe(event_type, recorded.append)
    return recorded


def types_of(events: list[SystemEvent]) -> list[SystemEventType]:
    return [event.event_type for event in events]
