"""Service Registry and runtime-scope invariant enforcement."""

import pytest

from paios.domain.entities.event import Event
from paios.domain.enums import EventStatus
from paios.domain.value_objects.identifiers import (
    ContextWindowId,
    EventId,
    UserId,
)
from paios.runtime.exceptions import RuntimeInvariantError, ServiceRegistryError
from paios.runtime.services import InvariantChecker, ServiceRegistry

from tests.runtime.conftest import at, build_active_window, build_started_event


def build_scheduled_event(
    event_id: str, user_id: str = "user_001", window_id: str = "win_x"
) -> Event:
    event = Event(
        event_id=EventId(event_id),
        user_id=UserId(user_id),
        context_window_id=ContextWindowId(window_id),
        category="study",
        description="Scheduled session",
    )
    event.transition_to(EventStatus.SCHEDULED, at(1))
    return event


class TestServiceRegistry:
    def test_register_and_get(self):
        registry = ServiceRegistry()
        service = object()
        registry.register("clock", service)
        assert registry.get("clock") is service
        assert registry.contains("clock")
        assert registry.names() == ("clock",)

    def test_duplicate_registration_rejected(self):
        registry = ServiceRegistry()
        registry.register("clock", object())
        with pytest.raises(ServiceRegistryError):
            registry.register("clock", object())

    def test_unknown_lookup_rejected(self):
        with pytest.raises(ServiceRegistryError):
            ServiceRegistry().get("missing")

    def test_remove(self):
        registry = ServiceRegistry()
        registry.register("clock", object())
        registry.remove("clock")
        assert not registry.contains("clock")
        with pytest.raises(ServiceRegistryError):
            registry.remove("clock")


class TestInvariantChecker:
    def test_clean_state_passes(self):
        checker = InvariantChecker()
        event = build_started_event()
        window = build_active_window()
        checker.enforce([event], [window])

    def test_empty_state_passes(self):
        InvariantChecker().enforce([], [])

    def test_two_running_events_same_user_rejected(self):
        first = build_started_event("evt_1", window_id="win_1")
        second = build_started_event("evt_2", window_id="win_2")
        with pytest.raises(RuntimeInvariantError):
            InvariantChecker().enforce([first, second], [])

    def test_running_events_for_different_users_pass(self):
        first = build_started_event("evt_1", user_id="user_001", window_id="win_1")
        second = build_started_event("evt_2", user_id="user_002", window_id="win_2")
        InvariantChecker().enforce([first, second], [])

    def test_two_active_windows_same_user_rejected(self):
        running = build_started_event("evt_1", window_id="win_1")
        scheduled = build_scheduled_event("evt_3", window_id="win_3")
        with pytest.raises(RuntimeInvariantError):
            InvariantChecker().enforce(
                [running, scheduled],
                [
                    build_active_window("win_1", "evt_1"),
                    build_active_window("win_3", "evt_3"),
                ],
            )

    def test_one_active_window_per_user_passes(self):
        first = build_started_event("evt_1", window_id="win_1")
        second = build_started_event(
            "evt_2", user_id="user_002", window_id="win_2"
        )
        InvariantChecker().enforce(
            [first, second],
            [
                build_active_window("win_1", "evt_1"),
                build_active_window("win_2", "evt_2"),
            ],
        )

    def test_shared_context_window_ownership_rejected(self):
        first = build_started_event("evt_1", window_id="win_shared")
        second = build_started_event(
            "evt_2", user_id="user_002", window_id="win_shared"
        )
        with pytest.raises(RuntimeInvariantError):
            InvariantChecker().enforce([first, second], [])
