"""Repository factory and data folder initialization.

Builds every aggregate repository over a single JsonStore rooted at the
data directory (default `.data/`, per ENTITY_RELATIONSHIPS.md - Local Data
Storage). `initialize()` creates the folder and seeds each missing aggregate
file with an empty JSON array so the documented layout is visible on disk.
Existing files are never touched.

`scheduler.json` from the documented layout is intentionally absent: the
Scheduler is a runtime component with no domain entity until its own
milestone.
"""

from pathlib import Path

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
    ResourceRepository,
    UserRepository,
)
from paios.repositories.json_repositories import (
    ALL_JSON_REPOSITORIES,
    ContextJsonRepository,
    ContextWindowJsonRepository,
    EventDisturberJsonRepository,
    EventJsonRepository,
    GoalJsonRepository,
    HabitJsonRepository,
    InsightJsonRepository,
    KnowledgeJsonRepository,
    PrincipleJsonRepository,
    ProgressJsonRepository,
    ProjectJsonRepository,
    RecommendationJsonRepository,
    ReflectionJsonRepository,
    ResourceJsonRepository,
    UserJsonRepository,
)
from paios.repositories.json_store import JsonStore


class RepositoryFactory:
    """Creates and caches one repository per aggregate over one data folder."""

    def __init__(self, data_dir: Path | str = ".data") -> None:
        self._store = JsonStore(data_dir)
        self._cache: dict[type, object] = {}

    @property
    def data_dir(self) -> Path:
        return self._store.data_dir

    def initialize(self) -> None:
        """Create the data folder and seed missing aggregate files with []."""
        self._store.initialize()
        for repository_cls in ALL_JSON_REPOSITORIES:
            path = self._store.path_for(repository_cls.FILENAME)
            if not path.exists():
                self._store.write(repository_cls.FILENAME, [])

    def _repository(self, repository_cls: type) -> object:
        if repository_cls not in self._cache:
            self._cache[repository_cls] = repository_cls(self._store)
        return self._cache[repository_cls]

    def users(self) -> UserRepository:
        return self._repository(UserJsonRepository)

    def principles(self) -> PrincipleRepository:
        return self._repository(PrincipleJsonRepository)

    def contexts(self) -> ContextRepository:
        return self._repository(ContextJsonRepository)

    def context_windows(self) -> ContextWindowRepository:
        return self._repository(ContextWindowJsonRepository)

    def events(self) -> EventRepository:
        return self._repository(EventJsonRepository)

    def projects(self) -> ProjectRepository:
        return self._repository(ProjectJsonRepository)

    def progress(self) -> ProgressRepository:
        return self._repository(ProgressJsonRepository)

    def resources(self) -> ResourceRepository:
        return self._repository(ResourceJsonRepository)

    def knowledge(self) -> KnowledgeRepository:
        return self._repository(KnowledgeJsonRepository)

    def recommendations(self) -> RecommendationRepository:
        return self._repository(RecommendationJsonRepository)

    def event_disturbers(self) -> EventDisturberRepository:
        return self._repository(EventDisturberJsonRepository)

    def reflections(self) -> ReflectionRepository:
        return self._repository(ReflectionJsonRepository)

    def insights(self) -> InsightRepository:
        return self._repository(InsightJsonRepository)

    def habits(self) -> HabitRepository:
        return self._repository(HabitJsonRepository)

    def goals(self) -> GoalRepository:
        return self._repository(GoalJsonRepository)
