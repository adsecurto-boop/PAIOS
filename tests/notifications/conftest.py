"""Notification test fixtures: a real bus, synthetic events, fakes."""

from datetime import datetime
from types import SimpleNamespace

import pytest

from paios.notifications import NotificationProvider
from paios.runtime.event_bus import EventBus
from paios.runtime.system_events import SystemEvent, SystemEventType

NOON = datetime(2026, 7, 21, 12, 0)
NIGHT = datetime(2026, 7, 21, 23, 0)


class RecordingProvider(NotificationProvider):
    def __init__(self, fail: bool = False) -> None:
        self.sent = []
        self._fail = fail

    @property
    def name(self) -> str:
        return "recording"

    def send(self, notification) -> None:
        if self._fail:
            raise RuntimeError("channel down")
        self.sent.append(notification)


@pytest.fixture
def bus():
    return EventBus()


def event(event_type: SystemEventType, payload=None, at=NOON) -> SystemEvent:
    return SystemEvent(event_type, at, payload or {})


def recommendation_entity(reason="Study ISTQB for 60 minutes", status="Pending"):
    return SimpleNamespace(
        reason=reason, status=SimpleNamespace(value=status)
    )


def event_entity(description="Deep work", status="Started"):
    return SimpleNamespace(
        description=description, status=SimpleNamespace(value=status)
    )


def disturber_entity(description="Phone call", severity="High"):
    return SimpleNamespace(
        description=description, severity=SimpleNamespace(value=severity)
    )
