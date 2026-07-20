"""Repository contract: CRUD, duplicates, reload, large datasets."""

import pytest

from paios.domain.enums import EventStatus
from paios.domain.errors import ImmutabilityViolationError
from paios.domain.value_objects.identifiers import EventId, UserId
from paios.repositories.errors import DuplicateEntity, EntityNotFound
from paios.repositories.json_repositories import (
    EventJsonRepository,
    RecommendationJsonRepository,
)
from paios.repositories.serialization import serialize_event

from tests.repositories.conftest import (
    at,
    build_completed_event,
    build_consumed_recommendation,
)


@pytest.fixture
def events(store) -> EventJsonRepository:
    return EventJsonRepository(store)


class TestSaveAndGet:
    def test_save_then_get_is_lossless(self, events):
        original = build_completed_event()
        events.save(original)
        loaded = events.get(original.event_id)
        assert loaded == original  # identity equality (same type + ID)
        assert serialize_event(loaded) == serialize_event(original)

    def test_save_duplicate_raises(self, events):
        event = build_completed_event()
        events.save(event)
        with pytest.raises(DuplicateEntity):
            events.save(build_completed_event())

    def test_get_missing_raises(self, events):
        with pytest.raises(EntityNotFound):
            events.get(EventId("evt_missing"))

    def test_exists(self, events):
        event = build_completed_event()
        assert not events.exists(event.event_id)
        events.save(event)
        assert events.exists(event.event_id)


class TestUpdateAndDelete:
    def test_update_overwrites(self, events):
        event = build_completed_event()
        events.save(event)
        event.transition_to(EventStatus.ARCHIVED, at(500))
        events.update(event)
        loaded = events.get(event.event_id)
        assert loaded.status is EventStatus.ARCHIVED
        assert len(loaded.transitions) == 8

    def test_update_missing_raises(self, events):
        with pytest.raises(EntityNotFound):
            events.update(build_completed_event())

    def test_delete(self, events):
        event = build_completed_event()
        events.save(event)
        events.delete(event.event_id)
        assert not events.exists(event.event_id)

    def test_delete_missing_raises(self, events):
        with pytest.raises(EntityNotFound):
            events.delete(EventId("evt_missing"))

    def test_delete_leaves_other_records(self, events):
        first = build_completed_event("evt_001")
        second = build_completed_event("evt_002")
        events.save(first)
        events.save(second)
        events.delete(first.event_id)
        assert [e.event_id for e in events.list()] == [second.event_id]


class TestListAndFind:
    def test_list_preserves_insertion_order(self, events):
        ids = ["evt_003", "evt_001", "evt_002"]
        for event_id in ids:
            events.save(build_completed_event(event_id))
        assert [str(e.event_id) for e in events.list()] == ids

    def test_find_by_attribute(self, events):
        events.save(build_completed_event("evt_001"))
        events.save(build_completed_event("evt_002"))
        found = events.find_by(user_id=UserId("user_001"))
        assert len(found) == 2
        assert events.find_by(user_id=UserId("user_999")) == []

    def test_find_by_derived_status(self, events):
        completed = build_completed_event("evt_001")
        archived = build_completed_event("evt_002")
        archived.transition_to(EventStatus.ARCHIVED, at(500))
        events.save(completed)
        events.save(archived)
        found = events.find_by(status=EventStatus.ARCHIVED)
        assert [e.event_id for e in found] == [archived.event_id]


class TestPersistenceAcrossInstances:
    def test_fresh_repository_sees_saved_data(self, store):
        EventJsonRepository(store).save(build_completed_event())
        loaded = EventJsonRepository(store).get(EventId("evt_001"))
        assert loaded.status is EventStatus.COMPLETED
        assert len(loaded.transitions) == 7

    def test_reloaded_entity_still_enforces_domain_guards(self, store):
        EventJsonRepository(store).save(build_completed_event())
        loaded = EventJsonRepository(store).get(EventId("evt_001"))
        with pytest.raises(ImmutabilityViolationError):
            loaded.actual_outcome = "rewritten"

    def test_multiple_aggregates_share_one_store(self, store):
        EventJsonRepository(store).save(build_completed_event())
        RecommendationJsonRepository(store).save(build_consumed_recommendation())
        assert (store.data_dir / "events.json").exists()
        assert (store.data_dir / "recommendations.json").exists()


class TestLargeDataset:
    def test_many_events_roundtrip(self, events):
        count = 150
        for index in range(count):
            events.save(build_completed_event(f"evt_{index:04d}"))
        loaded = events.list()
        assert len(loaded) == count
        assert all(e.status is EventStatus.COMPLETED for e in loaded)
        assert all(len(e.transitions) == 7 for e in loaded)
        sample = events.get(EventId("evt_0099"))
        assert sample.transitions[3].reason == "emergency call"
