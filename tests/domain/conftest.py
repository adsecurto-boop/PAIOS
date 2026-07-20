"""Shared factories and fixed timestamps for domain-layer tests.

The domain never reads the system clock — Current Time is always supplied by
the caller — so tests use fixed, deterministic datetimes.
"""

from datetime import datetime, timedelta

import pytest

from paios.domain.entities.context_window import ContextWindow
from paios.domain.entities.event import Event
from paios.domain.entities.recommendation import Recommendation
from paios.domain.value_objects.identifiers import (
    ContextId,
    ContextWindowId,
    EventId,
    RecommendationId,
    UserId,
)

T0 = datetime(2026, 7, 20, 9, 0)


def at(minutes: int) -> datetime:
    """A deterministic moment `minutes` after T0."""
    return T0 + timedelta(minutes=minutes)


@pytest.fixture
def user_id() -> UserId:
    return UserId("user_001")


@pytest.fixture
def make_event(user_id):
    def _make(
        event_id: str = "evt_001",
        context_window_id: str = "win_001",
        category: str = "study",
        description: str = "Studied ISTQB Chapter 3",
    ) -> Event:
        return Event(
            event_id=EventId(event_id),
            user_id=user_id,
            context_window_id=ContextWindowId(context_window_id),
            category=category,
            description=description,
        )

    return _make


@pytest.fixture
def make_window():
    def _make(
        window_id: str = "win_001",
        context_id: str = "ctx_001",
        event_id: str = "evt_001",
    ) -> ContextWindow:
        return ContextWindow(
            window_id=ContextWindowId(window_id),
            context_id=ContextId(context_id),
            event_id=EventId(event_id),
        )

    return _make


@pytest.fixture
def make_recommendation(user_id):
    def _make(
        recommendation_id: str = "rec_001",
        created_at: datetime = T0,
        expires_at: datetime | None = None,
    ) -> Recommendation:
        return Recommendation(
            recommendation_id=RecommendationId(recommendation_id),
            user_id=user_id,
            reason="Advance ISTQB certification project",
            created_at=created_at,
            expires_at=expires_at or at(60),
        )

    return _make
