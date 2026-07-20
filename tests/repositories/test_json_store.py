"""JsonStore: file I/O, directory creation, corruption handling."""

import json

import pytest

from paios.repositories.errors import SerializationError
from paios.repositories.json_store import JsonStore


class TestRead:
    def test_missing_file_means_no_records(self, store):
        assert store.read("events.json") == []

    def test_empty_file_means_no_records(self, store):
        store.initialize()
        store.path_for("events.json").write_text("", encoding="utf-8")
        assert store.read("events.json") == []

    def test_whitespace_only_file_means_no_records(self, store):
        store.initialize()
        store.path_for("events.json").write_text("  \n\t ", encoding="utf-8")
        assert store.read("events.json") == []

    def test_corrupted_json_raises(self, store):
        store.initialize()
        store.path_for("events.json").write_text(
            '[{"event_id": "evt_001", ', encoding="utf-8"
        )
        with pytest.raises(SerializationError, match="corrupted JSON"):
            store.read("events.json")

    def test_non_array_top_level_raises(self, store):
        store.initialize()
        store.path_for("events.json").write_text('{"a": 1}', encoding="utf-8")
        with pytest.raises(SerializationError, match="JSON array"):
            store.read("events.json")


class TestWrite:
    def test_write_creates_directory(self, store):
        assert not store.data_dir.exists()
        store.write("events.json", [{"event_id": "evt_001"}])
        assert store.data_dir.is_dir()
        assert store.path_for("events.json").exists()

    def test_roundtrip(self, store):
        records = [{"event_id": "evt_001", "n": 1}, {"event_id": "evt_002", "n": 2}]
        store.write("events.json", records)
        assert store.read("events.json") == records

    def test_overwrite_replaces_content(self, store):
        store.write("events.json", [{"event_id": "evt_001"}])
        store.write("events.json", [{"event_id": "evt_002"}])
        assert store.read("events.json") == [{"event_id": "evt_002"}]

    def test_no_temp_file_left_behind(self, store):
        store.write("events.json", [{"event_id": "evt_001"}])
        leftovers = [p.name for p in store.data_dir.iterdir() if "tmp" in p.name]
        assert leftovers == []

    def test_written_file_is_valid_readable_json(self, store):
        store.write("events.json", [{"event_id": "evt_001"}])
        raw = store.path_for("events.json").read_text(encoding="utf-8")
        assert json.loads(raw) == [{"event_id": "evt_001"}]

    def test_unserializable_records_raise(self, store):
        with pytest.raises(SerializationError):
            store.write("events.json", [{"bad": object()}])
