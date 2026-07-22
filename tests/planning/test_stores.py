"""Planning stores: durability, validation, identity (M20)."""

from datetime import datetime

import pytest

from paios.planning.stores import (
    EventMetadataStore,
    InboxStore,
    PlanningStoreError,
    RecurrenceStore,
    TemplateStore,
)

T0 = datetime(2026, 7, 22, 9, 0)


class TestInboxStore:
    def test_add_list_roundtrip_survives_reopen(self, tmp_path):
        store = InboxStore(tmp_path)
        record = store.add("Need haircut", T0)
        reopened = InboxStore(tmp_path)
        assert [item["id"] for item in reopened.list()] == [record["id"]]
        assert reopened.get(record["id"])["status"] == "open"

    def test_lifecycle_convert_archive_delete(self, tmp_path):
        store = InboxStore(tmp_path)
        first = store.add("Read chapter 3", T0)
        second = store.add("Call bank", T0)
        converted = store.mark_converted(first["id"], "goal:g1", T0)
        assert converted["status"] == "converted"
        assert converted["converted_to"] == "goal:g1"
        archived = store.archive(second["id"], T0)
        assert archived["status"] == "archived"
        store.delete(first["id"])
        assert [item["id"] for item in store.list()] == [second["id"]]

    def test_blank_text_rejected(self, tmp_path):
        with pytest.raises(PlanningStoreError):
            InboxStore(tmp_path).add("   ", T0)

    def test_unknown_id_raises(self, tmp_path):
        with pytest.raises(PlanningStoreError, match="Unknown"):
            InboxStore(tmp_path).get("inbox_missing")


class TestEventMetadataStore:
    def test_set_validates_each_field(self, tmp_path):
        store = EventMetadataStore(tmp_path)
        record = store.set(
            "ev1",
            {
                "tags": ["health", "errand", "health"],
                "deadline": "2026-07-23T18:00:00",
                "energy": "low",
                "estimated_duration_minutes": 30,
                "depends_on": ["ev0"],
            },
            T0,
        )
        assert record["tags"] == ["errand", "health"]  # deduped, sorted
        assert record["energy"] == "low"

    @pytest.mark.parametrize(
        "field,value",
        [
            ("tags", "not-a-list"),
            ("deadline", "not-a-date"),
            ("energy", "extreme"),
            ("estimated_duration_minutes", 0),
            ("estimated_duration_minutes", True),
            ("depends_on", [1, 2]),
        ],
    )
    def test_invalid_values_rejected(self, tmp_path, field, value):
        with pytest.raises(PlanningStoreError):
            EventMetadataStore(tmp_path).set("ev1", {field: value}, T0)

    def test_resolve_prefers_first_key_and_relink_moves(self, tmp_path):
        store = EventMetadataStore(tmp_path)
        store.set("rec1", {"tags": ["a"]}, T0)
        assert store.resolve("ev1", "rec1")["tags"] == ["a"]
        store.relink("rec1", "ev1")
        assert store.get("rec1") is None
        assert store.get("ev1")["key"] == "ev1"


class TestTemplateStore:
    def test_add_get_delete(self, tmp_path):
        store = TemplateStore(tmp_path)
        record = store.add(
            "Gym", "Gym session", T0, metadata={"energy": "high"}
        )
        assert store.get(record["id"])["metadata"] == {"energy": "high"}
        store.delete(record["id"])
        assert store.list() == []


class TestRecurrenceStore:
    def test_add_normalizes_days_and_time(self, tmp_path):
        store = RecurrenceStore(tmp_path)
        record = store.add(
            "Temple", "7:30", ["Sunday", "wed", "sun"], T0, T0
        )
        assert record["time_of_day"] == "07:30"
        assert record["days"] == ["wed", "sun"]

    @pytest.mark.parametrize(
        "time_of_day,days",
        [("25:00", ["mon"]), ("nope", ["mon"]), ("07:30", []),
         ("07:30", ["blursday"])],
    )
    def test_invalid_rules_rejected(self, tmp_path, time_of_day, days):
        with pytest.raises(PlanningStoreError):
            RecurrenceStore(tmp_path).add("X", time_of_day, days, T0, T0)
