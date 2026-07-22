"""Planning stores: synchronous write-through JSON files.

Four small stores, one file each under ``<data_dir>/planning/``:

    inbox.json        captured items awaiting triage
    metadata.json     per-event sidecar (tags/deadline/energy/duration/
                      dependencies) keyed by event id — falls back to the
                      originating recommendation id before materialization
    templates.json    named event templates
    recurrences.json  recurrence rules expanded into user intents

Records are plain dicts (JSON-shaped end to end). The stores validate
syntax and identity only; they hold no scheduling opinions. Every
timestamp is supplied by the caller (clock discipline, C6).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path


class PlanningStoreError(Exception):
    """A store-level failure (unknown id, malformed record)."""


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class _JsonFileStore:
    """One JSON document, read fresh and written whole on every change."""

    def __init__(self, path: Path, root_key: str) -> None:
        self._path = path
        self._root_key = root_key

    def _load(self) -> dict:
        if not self._path.is_file():
            return {self._root_key: {}}
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise PlanningStoreError(
                f"Cannot read {self._path.name}: {error}"
            ) from error
        if not isinstance(payload, dict) or self._root_key not in payload:
            return {self._root_key: {}}
        return payload

    def _save(self, payload: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(payload, indent=2, sort_keys=True)
        self._path.write_text(serialized, encoding="utf-8")

    def _records(self) -> dict:
        return self._load()[self._root_key]

    def _put(self, key: str, record: dict) -> None:
        payload = self._load()
        payload[self._root_key][key] = record
        self._save(payload)

    def _delete(self, key: str) -> None:
        payload = self._load()
        if key not in payload[self._root_key]:
            raise PlanningStoreError(f"Unknown id: {key}")
        del payload[self._root_key][key]
        self._save(payload)


def _require_text(value, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PlanningStoreError(f"'{field}' must be a non-empty string")
    return value.strip()


class InboxStore(_JsonFileStore):
    """Captured thoughts awaiting triage. Statuses: open, converted,
    archived. Deletion is real here — inbox items are scratch capture,
    not Domain evidence."""

    STATUSES = ("open", "converted", "archived")

    def __init__(self, planning_dir: Path) -> None:
        super().__init__(planning_dir / "inbox.json", "items")

    def add(self, text: str, at: datetime) -> dict:
        record = {
            "id": _new_id("inbox"),
            "text": _require_text(text, "text"),
            "status": "open",
            "created_at": at.isoformat(),
            "converted_to": None,
        }
        self._put(record["id"], record)
        return record

    def list(self, status: str | None = None) -> list[dict]:
        records = sorted(
            self._records().values(), key=lambda item: item["created_at"]
        )
        if status is None:
            return records
        return [item for item in records if item["status"] == status]

    def get(self, item_id: str) -> dict:
        record = self._records().get(item_id)
        if record is None:
            raise PlanningStoreError(f"Unknown inbox item: {item_id}")
        return record

    def mark_converted(
        self, item_id: str, converted_to: str, at: datetime
    ) -> dict:
        record = self.get(item_id)
        record["status"] = "converted"
        record["converted_to"] = converted_to
        record["converted_at"] = at.isoformat()
        self._put(item_id, record)
        return record

    def archive(self, item_id: str, at: datetime) -> dict:
        record = self.get(item_id)
        record["status"] = "archived"
        record["archived_at"] = at.isoformat()
        self._put(item_id, record)
        return record

    def delete(self, item_id: str) -> None:
        self._delete(item_id)


#: Energy levels the sidecar accepts (display/AI vocabulary, not Domain).
ENERGY_LEVELS = ("low", "medium", "high")


class EventMetadataStore(_JsonFileStore):
    """Sidecar metadata keyed by event id (or recommendation id until the
    Scheduler materializes the intent). The Domain never sees this."""

    FIELDS = (
        "tags",
        "deadline",
        "energy",
        "estimated_duration_minutes",
        "depends_on",
    )

    def __init__(self, planning_dir: Path) -> None:
        super().__init__(planning_dir / "metadata.json", "metadata")

    def set(self, key: str, values: dict, at: datetime) -> dict:
        record = self.get(key) or {"key": key}
        for field in self.FIELDS:
            if field in values:
                record[field] = self._validated(field, values[field])
        record["updated_at"] = at.isoformat()
        self._put(key, record)
        return record

    def get(self, key: str) -> dict | None:
        return self._records().get(key)

    def resolve(self, *keys: str | None) -> dict | None:
        """First record found under any supplied key (event id first,
        then originating recommendation id)."""
        for key in keys:
            if key is None:
                continue
            record = self.get(str(key))
            if record is not None:
                return record
        return None

    def relink(self, old_key: str, new_key: str) -> None:
        """Move a record captured pre-materialization (recommendation id)
        onto the materialized event id."""
        record = self.get(old_key)
        if record is None:
            return
        record["key"] = new_key
        payload = self._load()
        payload["metadata"].pop(old_key, None)
        payload["metadata"][new_key] = record
        self._save(payload)

    def all(self) -> dict:
        return dict(self._records())

    @staticmethod
    def _validated(field: str, value):
        if field == "tags":
            if not isinstance(value, list) or any(
                not isinstance(tag, str) for tag in value
            ):
                raise PlanningStoreError("'tags' must be a list of strings")
            return sorted({tag.strip() for tag in value if tag.strip()})
        if field == "deadline":
            if value is None:
                return None
            try:
                datetime.fromisoformat(str(value))
            except ValueError as error:
                raise PlanningStoreError(
                    "'deadline' must be an ISO datetime"
                ) from error
            return str(value)
        if field == "energy":
            if value is None:
                return None
            if value not in ENERGY_LEVELS:
                raise PlanningStoreError(
                    f"'energy' must be one of {ENERGY_LEVELS}"
                )
            return value
        if field == "estimated_duration_minutes":
            if value is None:
                return None
            if not isinstance(value, int) or isinstance(value, bool) or (
                not 1 <= value <= 24 * 60
            ):
                raise PlanningStoreError(
                    "'estimated_duration_minutes' must be an integer "
                    "between 1 and 1440"
                )
            return value
        if field == "depends_on":
            if not isinstance(value, list) or any(
                not isinstance(item, str) for item in value
            ):
                raise PlanningStoreError(
                    "'depends_on' must be a list of event/recommendation ids"
                )
            return sorted(set(value))
        raise PlanningStoreError(f"Unknown metadata field: {field}")


class TemplateStore(_JsonFileStore):
    """Named event templates: a title plus default metadata, instantiated
    into user intents on demand."""

    def __init__(self, planning_dir: Path) -> None:
        super().__init__(planning_dir / "templates.json", "templates")

    def add(
        self,
        name: str,
        title: str,
        at: datetime,
        category: str = "planned",
        metadata: dict | None = None,
    ) -> dict:
        record = {
            "id": _new_id("tpl"),
            "name": _require_text(name, "name"),
            "title": _require_text(title, "title"),
            "category": _require_text(category, "category"),
            "metadata": metadata or {},
            "created_at": at.isoformat(),
        }
        self._put(record["id"], record)
        return record

    def list(self) -> list[dict]:
        return sorted(self._records().values(), key=lambda item: item["name"])

    def get(self, template_id: str) -> dict:
        record = self._records().get(template_id)
        if record is None:
            raise PlanningStoreError(f"Unknown template: {template_id}")
        return record

    def delete(self, template_id: str) -> None:
        self._delete(template_id)


#: Weekday tokens accepted by recurrence rules, Monday-first.
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


class RecurrenceStore(_JsonFileStore):
    """Recurrence rules. Expansion (see PlanningService) turns a due rule
    into one user intent and advances ``next_run`` — the rule never
    creates Events itself; the Scheduler does, via the intent path."""

    def __init__(self, planning_dir: Path) -> None:
        super().__init__(planning_dir / "recurrences.json", "recurrences")

    def add(
        self,
        title: str,
        time_of_day: str,
        days: list[str],
        first_run: datetime,
        at: datetime,
        category: str = "recurring",
        metadata: dict | None = None,
    ) -> dict:
        hour, minute = self._parse_time(time_of_day)
        normalized_days = self._validated_days(days)
        record = {
            "id": _new_id("rec"),
            "title": _require_text(title, "title"),
            "category": _require_text(category, "category"),
            "time_of_day": f"{hour:02d}:{minute:02d}",
            "days": normalized_days,
            "next_run": first_run.isoformat(),
            "enabled": True,
            "metadata": metadata or {},
            "created_at": at.isoformat(),
        }
        self._put(record["id"], record)
        return record

    def list(self) -> list[dict]:
        return sorted(self._records().values(), key=lambda item: item["id"])

    def get(self, rule_id: str) -> dict:
        record = self._records().get(rule_id)
        if record is None:
            raise PlanningStoreError(f"Unknown recurrence: {rule_id}")
        return record

    def set_next_run(self, rule_id: str, next_run: datetime) -> dict:
        record = self.get(rule_id)
        record["next_run"] = next_run.isoformat()
        self._put(rule_id, record)
        return record

    def delete(self, rule_id: str) -> None:
        self._delete(rule_id)

    @staticmethod
    def _parse_time(time_of_day: str) -> tuple[int, int]:
        try:
            hour_text, minute_text = str(time_of_day).split(":")
            hour, minute = int(hour_text), int(minute_text)
        except ValueError as error:
            raise PlanningStoreError(
                "'time_of_day' must be HH:MM"
            ) from error
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise PlanningStoreError("'time_of_day' must be a valid time")
        return hour, minute

    @staticmethod
    def _validated_days(days: list[str]) -> list[str]:
        if not isinstance(days, list) or not days:
            raise PlanningStoreError(
                f"'days' must be a non-empty list from {WEEKDAYS}"
            )
        normalized = []
        for day in days:
            token = str(day).strip().lower()[:3]
            if token not in WEEKDAYS:
                raise PlanningStoreError(f"Unknown weekday: {day!r}")
            if token not in normalized:
                normalized.append(token)
        return sorted(normalized, key=WEEKDAYS.index)
