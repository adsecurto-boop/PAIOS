"""RepositoryFactory: data folder initialization and repository wiring."""

import json
from pathlib import Path

from paios.domain.value_objects.identifiers import EventId
from paios.repositories.factory import RepositoryFactory
from paios.repositories.json_repositories import ALL_JSON_REPOSITORIES

from tests.repositories.conftest import (
    build_completed_event,
    build_context,
    build_user,
)

EXPECTED_FILES = {
    "users.json",
    "principles.json",
    "contexts.json",
    "context_windows.json",
    "events.json",
    "projects.json",
    "progress.json",
    "resources.json",
    "knowledge.json",
    "recommendations.json",
    "event_disturbers.json",
    "reflections.json",
    "insights.json",
    "habits.json",
    "goals.json",
}


class TestInitialization:
    def test_initialize_creates_folder_and_all_aggregate_files(self, tmp_path):
        factory = RepositoryFactory(tmp_path / "data")
        factory.initialize()
        created = {p.name for p in (tmp_path / "data").iterdir()}
        assert created == EXPECTED_FILES
        for name in created:
            content = json.loads(
                (tmp_path / "data" / name).read_text(encoding="utf-8")
            )
            assert content == []

    def test_one_file_per_aggregate(self):
        assert len(ALL_JSON_REPOSITORIES) == len(EXPECTED_FILES) == 15
        assert {
            cls.FILENAME for cls in ALL_JSON_REPOSITORIES
        } == EXPECTED_FILES

    def test_initialize_never_clobbers_existing_data(self, tmp_path):
        factory = RepositoryFactory(tmp_path / "data")
        factory.events().save(build_completed_event())
        factory.initialize()
        assert factory.events().exists(EventId("evt_001"))

    def test_default_data_dir_is_dot_data(self):
        assert RepositoryFactory().data_dir == Path(".data")


class TestWiring:
    def test_repositories_are_cached(self, tmp_path):
        factory = RepositoryFactory(tmp_path / "data")
        assert factory.events() is factory.events()
        assert factory.users() is factory.users()

    def test_end_to_end_across_aggregates(self, tmp_path):
        factory = RepositoryFactory(tmp_path / "data")
        factory.initialize()
        factory.users().save(build_user())
        factory.contexts().save(build_context())
        factory.events().save(build_completed_event())
        assert len(factory.users().list()) == 1
        assert len(factory.contexts().list()) == 1
        assert len(factory.events().list()) == 1
