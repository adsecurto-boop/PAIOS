"""M20 client methods: one method per endpoint, right verb, right path.

A recording fake transport replaces ``_request`` — no server, no
socket; these tests pin the wire contract each method speaks.
"""

from paios_gui import ApiClient


class RecordingClient(ApiClient):
    """ApiClient with the transport swapped for a call recorder."""

    def __init__(self, responses: dict | None = None) -> None:
        super().__init__("http://test")
        self.calls: list[tuple] = []
        self._responses = responses or {}

    def _request(self, method: str, path: str, body=None):
        self.calls.append((method, path, body))
        return self._responses.get((method, path), {})

    @property
    def last(self):
        return self.calls[-1]


class TestEventAuthoring:
    def test_create_event_posts_events(self):
        client = RecordingClient()
        client.create_event(
            "Deep work",
            suggested_time="2026-07-23T09:00:00",
            priority=2.0,
            metadata={"energy": "high"},
        )
        method, path, body = client.last
        assert (method, path) == ("POST", "/events")
        assert body == {
            "title": "Deep work",
            "suggested_time": "2026-07-23T09:00:00",
            "priority": 2.0,
            "metadata": {"energy": "high"},
        }

    def test_create_event_drops_none_fields(self):
        client = RecordingClient()
        client.create_event("Bare", suggested_time=None, metadata=None)
        assert client.last == ("POST", "/events", {"title": "Bare"})

    def test_edit_event_puts_event(self):
        client = RecordingClient()
        client.edit_event("ev1", "New title", priority=1.0)
        assert client.last == (
            "PUT", "/events/ev1", {"title": "New title", "priority": 1.0}
        )

    def test_duplicate_event(self):
        client = RecordingClient()
        client.duplicate_event("ev1", suggested_time="2026-07-24T08:00:00")
        assert client.last == (
            "POST",
            "/events/ev1/duplicate",
            {"suggested_time": "2026-07-24T08:00:00"},
        )
        client.duplicate_event("ev1")
        assert client.last == ("POST", "/events/ev1/duplicate", {})

    def test_archive_event(self):
        client = RecordingClient()
        client.archive_event("ev1")
        assert client.last == ("POST", "/events/ev1/archive", {})

    def test_event_metadata_get_and_put(self):
        client = RecordingClient()
        client.get_event_metadata("ev1")
        assert client.last == ("GET", "/events/ev1/metadata", None)
        client.set_event_metadata("ev1", {"tags": ["a"]})
        assert client.last == (
            "PUT", "/events/ev1/metadata", {"tags": ["a"]}
        )


class TestPlanTemplatesRecurrences:
    def test_get_plan(self):
        client = RecordingClient(
            {("GET", "/plan"): {"created_at": None, "entries": []}}
        )
        assert client.get_plan() == {"created_at": None, "entries": []}
        assert client.last == ("GET", "/plan", None)

    def test_templates_roundtrip(self):
        client = RecordingClient(
            {("GET", "/templates"): {"templates": [{"id": "t1"}]}}
        )
        assert client.list_templates() == [{"id": "t1"}]
        client.create_template(
            "Morning", "Meditate", category="routine", metadata={"x": 1}
        )
        assert client.last == (
            "POST",
            "/templates",
            {
                "name": "Morning",
                "title": "Meditate",
                "category": "routine",
                "metadata": {"x": 1},
            },
        )
        client.delete_template("t1")
        assert client.last == ("DELETE", "/templates/t1", None)
        client.instantiate_template(
            "t1", suggested_time="2026-07-23T07:00:00"
        )
        assert client.last == (
            "POST",
            "/templates/t1/instantiate",
            {"suggested_time": "2026-07-23T07:00:00"},
        )

    def test_recurrences_roundtrip(self):
        client = RecordingClient(
            {("GET", "/recurrences"): {"recurrences": []}}
        )
        assert client.list_recurrences() == []
        client.create_recurrence("Gym", "18:00", ["mon", "wed"])
        assert client.last == (
            "POST",
            "/recurrences",
            {"title": "Gym", "time_of_day": "18:00", "days": ["mon", "wed"]},
        )
        client.delete_recurrence("r1")
        assert client.last == ("DELETE", "/recurrences/r1", None)


class TestInbox:
    def test_inbox_roundtrip(self):
        client = RecordingClient({("GET", "/inbox"): {"items": []}})
        assert client.list_inbox() == []
        client.add_inbox("Buy milk")
        assert client.last == ("POST", "/inbox", {"text": "Buy milk"})
        client.convert_inbox("i1", "goal", title="Milk goal")
        assert client.last == (
            "POST",
            "/inbox/i1/convert",
            {"to": "goal", "title": "Milk goal"},
        )
        client.archive_inbox("i1")
        assert client.last == ("POST", "/inbox/i1/archive", {})
        client.delete_inbox("i1")
        assert client.last == ("DELETE", "/inbox/i1", None)


class TestAssistantAndBackups:
    def test_assistant_endpoints(self):
        client = RecordingClient()
        client.assistant_status()
        assert client.last == ("GET", "/assistant/status", None)
        client.assistant_plan("Tomorrow\nTemple")
        assert client.last == (
            "POST", "/assistant/plan", {"text": "Tomorrow\nTemple"}
        )
        client.assistant_explain_day()
        assert client.last == ("POST", "/assistant/explain-day", {})

    def test_backup_endpoints(self):
        client = RecordingClient({("GET", "/backups"): {"backups": []}})
        assert client.list_backups() == []
        client.create_backup()
        assert client.last == ("POST", "/backups", {})
        client.restore_backup("paios-2026.zip")
        assert client.last == (
            "POST", "/backups/restore", {"archive": "paios-2026.zip"}
        )
