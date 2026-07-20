"""System Event Bus: publish/subscribe, dispatch order, immutability."""

import pytest

from paios.runtime.event_bus import EventBus
from paios.runtime.system_events import (
    KERNEL_EVENTS,
    RESERVED_EVENTS,
    SCHEDULER_EVENTS,
    SystemEvent,
    SystemEventType,
)

from tests.runtime.conftest import T0


def make_event(event_type=SystemEventType.RUNTIME_READY, **payload) -> SystemEvent:
    return SystemEvent(event_type=event_type, occurred_at=T0, payload=payload)


class TestEventBus:
    def test_subscriber_receives_published_event(self):
        bus = EventBus()
        received = []
        bus.subscribe(SystemEventType.RUNTIME_READY, received.append)
        event = make_event()
        bus.publish(event)
        assert received == [event]

    def test_dispatch_order_is_subscription_order(self):
        bus = EventBus()
        order = []
        bus.subscribe(SystemEventType.RUNTIME_READY, lambda e: order.append("first"))
        bus.subscribe(SystemEventType.RUNTIME_READY, lambda e: order.append("second"))
        bus.publish(make_event())
        assert order == ["first", "second"]

    def test_topics_are_isolated(self):
        bus = EventBus()
        ready, paused = [], []
        bus.subscribe(SystemEventType.RUNTIME_READY, ready.append)
        bus.subscribe(SystemEventType.RUNTIME_PAUSED, paused.append)
        bus.publish(make_event(SystemEventType.RUNTIME_PAUSED))
        assert ready == []
        assert len(paused) == 1

    def test_unsubscribe(self):
        bus = EventBus()
        received = []
        bus.subscribe(SystemEventType.RUNTIME_READY, received.append)
        bus.unsubscribe(SystemEventType.RUNTIME_READY, received.append)
        bus.publish(make_event())
        assert received == []
        assert bus.subscriber_count(SystemEventType.RUNTIME_READY) == 0

    def test_publish_without_subscribers_is_harmless(self):
        EventBus().publish(make_event())


class TestSystemEvents:
    def test_payload_is_immutable(self):
        event = make_event(service="clock")
        with pytest.raises(TypeError):
            event.payload["service"] = "other"

    def test_catalogs_partition_the_vocabulary(self):
        assert KERNEL_EVENTS | SCHEDULER_EVENTS | RESERVED_EVENTS == frozenset(
            SystemEventType
        )
        assert not KERNEL_EVENTS & RESERVED_EVENTS
        assert not KERNEL_EVENTS & SCHEDULER_EVENTS
        assert not SCHEDULER_EVENTS & RESERVED_EVENTS
        assert len(KERNEL_EVENTS) == 11
        assert len(SCHEDULER_EVENTS) == 1

    def test_reserved_catalog_matches_behavioral_architecture(self):
        reserved_names = {event_type.value for event_type in RESERVED_EVENTS}
        assert reserved_names == {
            "ContextChanged",
            "EventStateChanged",
            "ResourceThresholdCrossed",
            "DisturbanceDetected",
            "TimeProgressed",
            "RecommendationGenerated",
            "PlanUpdated",
            "EventCompleted",
            "ReflectionCreated",
            "InsightGenerated",
            "HabitDetected",
        }
