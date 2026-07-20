"""Repository interfaces (Repository Pattern).

One interface per aggregate, all sharing the same contract. Repositories
only persist — they contain no business logic, no policy evaluation, and no
runtime behavior. The domain never depends on these interfaces; application
layers (later milestones) depend on the abstractions, not the JSON
implementations (Dependency Inversion).
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from paios.domain.entities.context import Context
from paios.domain.entities.context_window import ContextWindow
from paios.domain.entities.event import Event
from paios.domain.entities.event_disturber import EventDisturber
from paios.domain.entities.goal import Goal
from paios.domain.entities.habit import Habit
from paios.domain.entities.insight import Insight
from paios.domain.entities.knowledge import Knowledge
from paios.domain.entities.principle import Principle
from paios.domain.entities.progress import Progress
from paios.domain.entities.project import Project
from paios.domain.entities.recommendation import Recommendation
from paios.domain.entities.reflection import Reflection
from paios.domain.entities.resource import Resource
from paios.domain.entities.user import User
from paios.domain.value_objects.identifiers import (
    ContextId,
    ContextWindowId,
    EventDisturberId,
    EventId,
    GoalId,
    HabitId,
    Identifier,
    InsightId,
    KnowledgeId,
    PrincipleId,
    ProgressId,
    ProjectId,
    RecommendationId,
    ReflectionId,
    ResourceId,
    UserId,
)

E = TypeVar("E")
I = TypeVar("I", bound=Identifier)


class Repository(ABC, Generic[E, I]):
    """Persistence contract shared by every aggregate repository.

    Raises (from paios.repositories.errors):
    - ``DuplicateEntity`` from ``save`` when the identifier already exists
    - ``EntityNotFound`` from ``get``/``update``/``delete`` when it does not
    - ``SerializationError`` when stored data cannot be read back losslessly
    """

    @abstractmethod
    def save(self, entity: E) -> None:
        """Persist a new entity; fails on a duplicate identifier."""

    @abstractmethod
    def get(self, entity_id: I) -> E:
        """Load one entity by identifier."""

    @abstractmethod
    def update(self, entity: E) -> None:
        """Overwrite the persisted state of an existing entity."""

    @abstractmethod
    def delete(self, entity_id: I) -> None:
        """Remove one entity by identifier."""

    @abstractmethod
    def list(self) -> "list[E]":
        """Load every persisted entity, in stored order."""

    @abstractmethod
    def exists(self, entity_id: I) -> bool:
        """True when an entity with this identifier is persisted."""

    @abstractmethod
    def find_by(self, **criteria: object) -> "list[E]":
        """Load entities whose attributes equal every given criterion.

        Pure attribute-equality filtering — a persistence query, not a
        business rule (e.g. ``find_by(user_id=..., status=...)``).
        """


class UserRepository(Repository[User, UserId], ABC):
    pass


class PrincipleRepository(Repository[Principle, PrincipleId], ABC):
    pass


class ContextRepository(Repository[Context, ContextId], ABC):
    pass


class ContextWindowRepository(Repository[ContextWindow, ContextWindowId], ABC):
    pass


class EventRepository(Repository[Event, EventId], ABC):
    pass


class ProjectRepository(Repository[Project, ProjectId], ABC):
    pass


class ProgressRepository(Repository[Progress, ProgressId], ABC):
    pass


class ResourceRepository(Repository[Resource, ResourceId], ABC):
    pass


class KnowledgeRepository(Repository[Knowledge, KnowledgeId], ABC):
    pass


class RecommendationRepository(Repository[Recommendation, RecommendationId], ABC):
    pass


class EventDisturberRepository(Repository[EventDisturber, EventDisturberId], ABC):
    pass


class ReflectionRepository(Repository[Reflection, ReflectionId], ABC):
    pass


class InsightRepository(Repository[Insight, InsightId], ABC):
    pass


class HabitRepository(Repository[Habit, HabitId], ABC):
    pass


class GoalRepository(Repository[Goal, GoalId], ABC):
    pass
