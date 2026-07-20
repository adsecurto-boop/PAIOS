"""JSON implementations of the repository interfaces.

One JSON array file per aggregate (ENTITY_RELATIONSHIPS.md - Local Data
Storage). A shared generic base implements the whole Repository contract;
each concrete class binds a filename, an identifier field, and the
aggregate's serializer/deserializer pair. No business logic lives here.
"""

from typing import Callable, ClassVar, Generic, TypeVar

from paios.domain.value_objects.identifiers import Identifier
from paios.repositories.errors import DuplicateEntity, EntityNotFound
from paios.repositories.interfaces import (
    ContextRepository,
    ContextWindowRepository,
    EventDisturberRepository,
    EventRepository,
    GoalRepository,
    HabitRepository,
    InsightRepository,
    KnowledgeRepository,
    PrincipleRepository,
    ProgressRepository,
    ProjectRepository,
    RecommendationRepository,
    ReflectionRepository,
    Repository,
    ResourceRepository,
    UserRepository,
)
from paios.repositories.json_store import JsonStore
from paios.repositories.serialization import (
    deserialize_context,
    deserialize_context_window,
    deserialize_event,
    deserialize_event_disturber,
    deserialize_goal,
    deserialize_habit,
    deserialize_insight,
    deserialize_knowledge,
    deserialize_principle,
    deserialize_progress,
    deserialize_project,
    deserialize_recommendation,
    deserialize_reflection,
    deserialize_resource,
    deserialize_user,
)
from paios.repositories.serialization import (
    serialize_context,
    serialize_context_window,
    serialize_event,
    serialize_event_disturber,
    serialize_goal,
    serialize_habit,
    serialize_insight,
    serialize_knowledge,
    serialize_principle,
    serialize_progress,
    serialize_project,
    serialize_recommendation,
    serialize_reflection,
    serialize_resource,
    serialize_user,
)

E = TypeVar("E")
I = TypeVar("I", bound=Identifier)


class JsonRepository(Repository[E, I], Generic[E, I]):
    """Generic JSON-file repository; concrete classes bind the specifics."""

    FILENAME: ClassVar[str]
    ID_FIELD: ClassVar[str]
    _serialize: Callable[[E], dict]
    _deserialize: Callable[[dict], E]

    def __init__(self, store: JsonStore) -> None:
        self._store = store

    def _records(self) -> list[dict]:
        return self._store.read(self.FILENAME)

    def _write(self, records: list[dict]) -> None:
        self._store.write(self.FILENAME, records)

    def _id_of(self, entity: E) -> str:
        return str(getattr(entity, self.ID_FIELD))

    def save(self, entity: E) -> None:
        records = self._records()
        entity_id = self._id_of(entity)
        if any(record.get(self.ID_FIELD) == entity_id for record in records):
            raise DuplicateEntity(
                f"{type(entity).__name__} {entity_id!r} already exists in "
                f"{self.FILENAME}; use update() to overwrite"
            )
        records.append(type(self)._serialize(entity))
        self._write(records)

    def get(self, entity_id: I) -> E:
        wanted = str(entity_id)
        for record in self._records():
            if record.get(self.ID_FIELD) == wanted:
                return type(self)._deserialize(record)
        raise EntityNotFound(f"{wanted!r} not found in {self.FILENAME}")

    def update(self, entity: E) -> None:
        records = self._records()
        entity_id = self._id_of(entity)
        for index, record in enumerate(records):
            if record.get(self.ID_FIELD) == entity_id:
                records[index] = type(self)._serialize(entity)
                self._write(records)
                return
        raise EntityNotFound(
            f"{entity_id!r} not found in {self.FILENAME}; use save() first"
        )

    def delete(self, entity_id: I) -> None:
        wanted = str(entity_id)
        records = self._records()
        remaining = [r for r in records if r.get(self.ID_FIELD) != wanted]
        if len(remaining) == len(records):
            raise EntityNotFound(f"{wanted!r} not found in {self.FILENAME}")
        self._write(remaining)

    def list(self) -> "list[E]":
        return [type(self)._deserialize(record) for record in self._records()]

    def exists(self, entity_id: I) -> bool:
        wanted = str(entity_id)
        return any(
            record.get(self.ID_FIELD) == wanted for record in self._records()
        )

    def find_by(self, **criteria: object) -> "list[E]":
        return [
            entity
            for entity in self.list()
            if all(
                getattr(entity, attribute) == value
                for attribute, value in criteria.items()
            )
        ]


class UserJsonRepository(JsonRepository, UserRepository):
    FILENAME = "users.json"
    ID_FIELD = "user_id"
    _serialize = staticmethod(serialize_user)
    _deserialize = staticmethod(deserialize_user)


class PrincipleJsonRepository(JsonRepository, PrincipleRepository):
    FILENAME = "principles.json"
    ID_FIELD = "principle_id"
    _serialize = staticmethod(serialize_principle)
    _deserialize = staticmethod(deserialize_principle)


class ContextJsonRepository(JsonRepository, ContextRepository):
    FILENAME = "contexts.json"
    ID_FIELD = "context_id"
    _serialize = staticmethod(serialize_context)
    _deserialize = staticmethod(deserialize_context)


class ContextWindowJsonRepository(JsonRepository, ContextWindowRepository):
    FILENAME = "context_windows.json"
    ID_FIELD = "window_id"
    _serialize = staticmethod(serialize_context_window)
    _deserialize = staticmethod(deserialize_context_window)


class EventJsonRepository(JsonRepository, EventRepository):
    FILENAME = "events.json"
    ID_FIELD = "event_id"
    _serialize = staticmethod(serialize_event)
    _deserialize = staticmethod(deserialize_event)


class ProjectJsonRepository(JsonRepository, ProjectRepository):
    FILENAME = "projects.json"
    ID_FIELD = "project_id"
    _serialize = staticmethod(serialize_project)
    _deserialize = staticmethod(deserialize_project)


class ProgressJsonRepository(JsonRepository, ProgressRepository):
    FILENAME = "progress.json"
    ID_FIELD = "progress_id"
    _serialize = staticmethod(serialize_progress)
    _deserialize = staticmethod(deserialize_progress)


class ResourceJsonRepository(JsonRepository, ResourceRepository):
    FILENAME = "resources.json"
    ID_FIELD = "resource_id"
    _serialize = staticmethod(serialize_resource)
    _deserialize = staticmethod(deserialize_resource)


class KnowledgeJsonRepository(JsonRepository, KnowledgeRepository):
    FILENAME = "knowledge.json"
    ID_FIELD = "knowledge_id"
    _serialize = staticmethod(serialize_knowledge)
    _deserialize = staticmethod(deserialize_knowledge)


class RecommendationJsonRepository(JsonRepository, RecommendationRepository):
    FILENAME = "recommendations.json"
    ID_FIELD = "recommendation_id"
    _serialize = staticmethod(serialize_recommendation)
    _deserialize = staticmethod(deserialize_recommendation)


class EventDisturberJsonRepository(JsonRepository, EventDisturberRepository):
    FILENAME = "event_disturbers.json"
    ID_FIELD = "event_disturber_id"
    _serialize = staticmethod(serialize_event_disturber)
    _deserialize = staticmethod(deserialize_event_disturber)


class ReflectionJsonRepository(JsonRepository, ReflectionRepository):
    FILENAME = "reflections.json"
    ID_FIELD = "reflection_id"
    _serialize = staticmethod(serialize_reflection)
    _deserialize = staticmethod(deserialize_reflection)


class InsightJsonRepository(JsonRepository, InsightRepository):
    FILENAME = "insights.json"
    ID_FIELD = "insight_id"
    _serialize = staticmethod(serialize_insight)
    _deserialize = staticmethod(deserialize_insight)


class HabitJsonRepository(JsonRepository, HabitRepository):
    FILENAME = "habits.json"
    ID_FIELD = "habit_id"
    _serialize = staticmethod(serialize_habit)
    _deserialize = staticmethod(deserialize_habit)


class GoalJsonRepository(JsonRepository, GoalRepository):
    FILENAME = "goals.json"
    ID_FIELD = "goal_id"
    _serialize = staticmethod(serialize_goal)
    _deserialize = staticmethod(deserialize_goal)


#: Every concrete JSON repository, used by the factory and data initializer.
ALL_JSON_REPOSITORIES: tuple[type[JsonRepository], ...] = (
    UserJsonRepository,
    PrincipleJsonRepository,
    ContextJsonRepository,
    ContextWindowJsonRepository,
    EventJsonRepository,
    ProjectJsonRepository,
    ProgressJsonRepository,
    ResourceJsonRepository,
    KnowledgeJsonRepository,
    RecommendationJsonRepository,
    EventDisturberJsonRepository,
    ReflectionJsonRepository,
    InsightJsonRepository,
    HabitJsonRepository,
    GoalJsonRepository,
)
