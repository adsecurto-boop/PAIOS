"""Insight — distilled, reusable knowledge generated from a Reflection.

Insights originate from Reflections (ENTITY_RELATIONSHIPS.md); the source
Reflection is therefore a required reference. Immutable once created —
Insights are learning evidence, not editable state.
"""

from dataclasses import dataclass
from datetime import datetime

from paios.domain.value_objects.identifiers import InsightId, ReflectionId


@dataclass(frozen=True, slots=True)
class Insight:
    insight_id: InsightId
    source_reflection_id: ReflectionId
    created_at: datetime
    category: str | None = None
    confidence: float | None = None
    reusable: bool = False
