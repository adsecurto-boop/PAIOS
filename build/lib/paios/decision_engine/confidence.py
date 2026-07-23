"""Confidence (DECISION_ENGINE.md §7): appropriateness certainty.

Confidence is NOT probability — it measures how well a Recommendation
fits the current state, from deterministic factors the documents list:
pattern/fact strength, data completeness, Principle alignment, Resource
feasibility headroom, and historical support. Factors and thresholds are
Domain-Policy constants.
"""

from dataclasses import dataclass
from enum import Enum, unique
from types import MappingProxyType
from typing import Mapping

from paios.domain.enums import EventStatus, ResourceType
from paios.decision_engine.rules import Candidate
from paios.runtime.runtime_snapshot import RuntimeSnapshot

BASE_CONFIDENCE = 0.5
BONUS_STRONG_FACTS = 0.2  # two or more observed facts
BONUS_PRINCIPLE_ALIGNMENT = 0.15
BONUS_HISTORICAL_SUPPORT = 0.15
PENALTY_UNTRACKED_RESOURCE = 0.2  # energy needed but not tracked

HIGH_THRESHOLD = 0.75
MEDIUM_THRESHOLD = 0.45


@unique
class ConfidenceLevel(Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


@dataclass(frozen=True)
class Confidence:
    value: float
    level: ConfidenceLevel
    factors: Mapping[str, float]

    def __post_init__(self) -> None:
        object.__setattr__(self, "factors", MappingProxyType(dict(self.factors)))


def compute_confidence(
    snapshot: RuntimeSnapshot, candidate: Candidate
) -> Confidence:
    factors: dict[str, float] = {"base": BASE_CONFIDENCE}
    if len(candidate.facts) >= 2:
        factors["strong_fact_pattern"] = BONUS_STRONG_FACTS
    if candidate.aligned_principles:
        factors["principle_alignment"] = BONUS_PRINCIPLE_ALIGNMENT
    if any(
        event.status is EventStatus.COMPLETED
        and event.category == candidate.category
        for event in snapshot.events
    ):
        factors["historical_support"] = BONUS_HISTORICAL_SUPPORT
    if candidate.required_energy > 0 and not any(
        resource.type is ResourceType.ENERGY
        for resource in snapshot.resources
    ):
        factors["untracked_required_resource"] = -PENALTY_UNTRACKED_RESOURCE
    value = max(0.0, min(1.0, sum(factors.values())))
    if value >= HIGH_THRESHOLD:
        level = ConfidenceLevel.HIGH
    elif value >= MEDIUM_THRESHOLD:
        level = ConfidenceLevel.MEDIUM
    else:
        level = ConfidenceLevel.LOW
    return Confidence(value=value, level=level, factors=factors)
