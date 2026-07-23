"""System Event Bus — kernel-owned publish/subscribe.

Synchronous, deterministic dispatch in subscription order. The
architecture allows the Kernel to manage synchronous vs asynchronous
delivery (BEHAVIORAL_ARCHITECTURE.md section 12); Milestone 3 implements
the synchronous form — asynchronous delivery is a documented deferral, not
an omission. Handler exceptions propagate to the publisher: with no
production subscribers yet, silent swallowing would only hide defects.
"""

from typing import Callable

from paios.runtime.system_events import SystemEvent, SystemEventType

EventHandler = Callable[[SystemEvent], None]


class EventBus:
    """Publish/subscribe over SystemEventType topics."""

    def __init__(self) -> None:
        self._subscribers: dict[SystemEventType, list[EventHandler]] = {}

    def subscribe(
        self, event_type: SystemEventType, handler: EventHandler
    ) -> None:
        self._subscribers.setdefault(event_type, []).append(handler)

    def unsubscribe(
        self, event_type: SystemEventType, handler: EventHandler
    ) -> None:
        handlers = self._subscribers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    def subscriber_count(self, event_type: SystemEventType) -> int:
        return len(self._subscribers.get(event_type, []))

    def publish(self, event: SystemEvent) -> None:
        """Dispatch to every subscriber of the event's type, in order."""
        for handler in tuple(self._subscribers.get(event.event_type, [])):
            handler(event)
