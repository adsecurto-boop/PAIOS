"""Assistant test fixtures: duck-typed snapshot inputs and adapters."""

import json
from datetime import datetime
from types import SimpleNamespace

import pytest

from paios.assistant.adapters import LlmAdapter

T0 = datetime(2026, 7, 20, 9, 0)
T1 = datetime(2026, 7, 22, 9, 0)


class RecordingAdapter(LlmAdapter):
    """Returns a fixed contract-conforming reply; records every request."""

    def __init__(self, reply: str | None = None) -> None:
        self.requests = []
        self._reply = reply if reply is not None else json.dumps(
            {"answer": "A grounded answer.", "bullets": ["b1"], "confidence": 0.9}
        )

    @property
    def name(self) -> str:
        return "recording"

    def complete(self, request) -> str:
        self.requests.append(request)
        return self._reply


def enum_like(value: str):
    return SimpleNamespace(value=value)


@pytest.fixture
def recommendation():
    return SimpleNamespace(
        status=enum_like("Pending"),
        reason="Energy is low (10 points); rest to recover",
        priority=8.5,
        confidence_score=0.9,
        expires_at=T1,
    )


@pytest.fixture
def principle():
    return SimpleNamespace(
        name="Health first",
        category=enum_like("Health"),
        description="Recover before you push.",
    )


@pytest.fixture
def habit():
    return SimpleNamespace(
        name="Morning study", strength=0.7, current_trend="improving"
    )


def make_event(description, status="Completed", category="Work"):
    return SimpleNamespace(
        description=description,
        status=enum_like(status),
        category=category,
        start_time=T0,
        duration=SimpleNamespace(minutes=60),
        actual_outcome="done",
    )


@pytest.fixture
def events():
    return (
        make_event("Deep work"),
        make_event("Rest break", category="Recovery"),
    )


@pytest.fixture
def snapshot(events):
    return SimpleNamespace(
        created_at=T0,
        current_time=T0,
        execution_context=SimpleNamespace(),
        running_event=None,
        events=events,
        recommendations=(),
        goals=(),
        projects=(),
        resources=(),
        contexts=(),
        reflections=(),
        principles=(),
    )


@pytest.fixture
def later_snapshot(events):
    return SimpleNamespace(
        created_at=T1,
        current_time=T1,
        execution_context=SimpleNamespace(),
        running_event=make_event("Deep work", status="Started"),
        events=events + (make_event("Review notes"),),
        recommendations=(SimpleNamespace(reason="rest"),),
        goals=(),
        projects=(),
        resources=(),
        contexts=(),
        reflections=(),
        principles=(),
    )


@pytest.fixture
def learning_result():
    return SimpleNamespace(
        generated_at=T1,
        findings=(SimpleNamespace(description="Mornings are productive"),),
        trends=(SimpleNamespace(description="Focus rising week over week"),),
        insights=(SimpleNamespace(category="Focus", description="Guard 9-11am"),),
        candidate_principles=(),
        candidate_habit_changes=(),
    )


@pytest.fixture
def knowledge_items():
    return (
        SimpleNamespace(
            domain="Testing",
            topic="ISTQB",
            concept="Boundary analysis",
            confidence=0.4,
            revision_count=2,
            last_revision=T0,
        ),
        SimpleNamespace(
            domain="Languages",
            topic="Sanskrit",
            concept="Sandhi rules",
            confidence=0.8,
            revision_count=5,
            last_revision=T1,
        ),
    )


@pytest.fixture
def projects():
    return (
        SimpleNamespace(
            name="PAIOS", status=enum_like("Active"), description="Build it"
        ),
        SimpleNamespace(
            name="Garden", status=enum_like("Paused"), description="Replant"
        ),
    )


@pytest.fixture
def reflections():
    return (
        SimpleNamespace(
            created_at=T0,
            lesson_learned="Breaks work",
            improvement="Schedule them",
        ),
    )
