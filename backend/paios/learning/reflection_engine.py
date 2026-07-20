"""Reflection analysis and Insight generation.

Domain Insights REQUIRE a source Reflection (ENTITY_RELATIONSHIPS.md:
"Insights originate from Reflections") — so this module is the ONLY place
domain Insight entities are generated, one per qualifying Reflection, with
deterministic uuid5 identifiers and timestamps taken from the Reflection's
own created_at. Pattern discoveries without a Reflection stay learning-
layer Findings — never Insight entities.
"""

import uuid
from dataclasses import dataclass

from paios.domain.entities.insight import Insight
from paios.domain.value_objects.identifiers import InsightId
from paios.learning.extractor import category_of
from paios.learning.history import History

_INSIGHT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "paios://learning/insight")

#: A Reflection is "complete" when it captured both causal understanding
#: and a lesson — the fields DOMAIN_MODEL.md names as its purpose.
_QUALITY_FIELDS = ("root_cause", "lesson_learned")


@dataclass(frozen=True)
class ReflectionQuality:
    total: int
    complete: int
    with_lesson: int

    @property
    def completeness_ratio(self) -> float:
        return self.complete / self.total if self.total else 0.0


def deterministic_insight_id(reflection) -> InsightId:
    return InsightId(
        str(uuid.uuid5(_INSIGHT_NAMESPACE, str(reflection.reflection_id)))
    )


def analyze_reflections(
    history: History,
) -> tuple[tuple[Insight, ...], ReflectionQuality]:
    """Generate one Insight per Reflection that carries a lesson, plus a
    deterministic quality measure of the reflection practice itself."""
    events_by_id = {str(event.event_id): event for event in history.events}
    insights: list[Insight] = []
    complete = 0
    with_lesson = 0
    for reflection in sorted(
        history.reflections, key=lambda r: str(r.reflection_id)
    ):
        has_all_quality_fields = all(
            getattr(reflection, field) for field in _QUALITY_FIELDS
        )
        if has_all_quality_fields:
            complete += 1
        if reflection.lesson_learned:
            with_lesson += 1
            source_event = events_by_id.get(str(reflection.event_id))
            category = (
                category_of(source_event)
                if source_event is not None
                else "general"
            )
            insights.append(
                Insight(
                    insight_id=deterministic_insight_id(reflection),
                    source_reflection_id=reflection.reflection_id,
                    created_at=reflection.created_at,
                    category=category,
                    confidence=reflection.confidence,
                    reusable=has_all_quality_fields,
                )
            )
    quality = ReflectionQuality(
        total=len(history.reflections),
        complete=complete,
        with_lesson=with_lesson,
    )
    return tuple(insights), quality
