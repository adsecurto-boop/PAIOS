"""Typed identifiers for every domain entity.

Each entity gets its own identifier type so that, for example, an EventId can
never be passed where a ContextWindowId is expected. Identifiers are immutable
value objects; Event IDs in particular are immutable once assigned
(BUSINESS_RULES.md - Domain Invariants).
"""

import uuid
from dataclasses import dataclass

from paios.domain.errors import DomainValidationError


@dataclass(frozen=True, slots=True)
class Identifier:
    """Base identifier: a non-empty opaque string."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.strip():
            raise DomainValidationError(
                f"{type(self).__name__} requires a non-empty string value"
            )

    @classmethod
    def new(cls) -> "Identifier":
        return cls(str(uuid.uuid4()))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class UserId(Identifier):
    pass


@dataclass(frozen=True, slots=True)
class EventId(Identifier):
    pass


@dataclass(frozen=True, slots=True)
class ProjectId(Identifier):
    pass


@dataclass(frozen=True, slots=True)
class ContextId(Identifier):
    pass


@dataclass(frozen=True, slots=True)
class ContextWindowId(Identifier):
    pass


@dataclass(frozen=True, slots=True)
class PrincipleId(Identifier):
    pass


@dataclass(frozen=True, slots=True)
class ResourceId(Identifier):
    pass


@dataclass(frozen=True, slots=True)
class KnowledgeId(Identifier):
    pass


@dataclass(frozen=True, slots=True)
class RecommendationId(Identifier):
    pass


@dataclass(frozen=True, slots=True)
class ProgressId(Identifier):
    pass


@dataclass(frozen=True, slots=True)
class ReflectionId(Identifier):
    pass


@dataclass(frozen=True, slots=True)
class InsightId(Identifier):
    pass


@dataclass(frozen=True, slots=True)
class HabitId(Identifier):
    pass


@dataclass(frozen=True, slots=True)
class GoalId(Identifier):
    pass


@dataclass(frozen=True, slots=True)
class EventDisturberId(Identifier):
    pass
