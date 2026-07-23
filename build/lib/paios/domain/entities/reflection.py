"""Reflection — the user's retrospective interpretation of an Event.

Domain Invariant: a Reflection requires an Event — it cannot exist
independently (BUSINESS_RULES.md). Enforced structurally: ``event_id`` and
``context_window_id`` are required constructor arguments. Reflections are
part of immutable History, hence frozen.
"""

from dataclasses import dataclass
from datetime import datetime

from paios.domain.errors import DomainValidationError
from paios.domain.value_objects.identifiers import (
    ContextWindowId,
    EventId,
    ReflectionId,
)


@dataclass(frozen=True, slots=True)
class Reflection:
    reflection_id: ReflectionId
    event_id: EventId
    context_window_id: ContextWindowId
    created_at: datetime
    facts: str | None = None
    interpretation: str | None = None
    root_cause: str | None = None
    lesson_learned: str | None = None
    improvement: str | None = None
    confidence: float | None = None

    def __post_init__(self) -> None:
        if self.event_id is None or self.context_window_id is None:
            raise DomainValidationError(
                "A Reflection requires an Event and its Context Window"
            )
