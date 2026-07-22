"""Event authoring: the New/Edit dialog's payload discipline (metadata
only when set), the card board's grouping/filtering, and the authoring
round trips against the live server.
"""

from paios_gui.dialogs import EventDialog
from paios_gui.events_page import EventsPage

from tests.gui.test_client_m20 import RecordingClient
from tests.gui.test_planning_page import StubWindow

EVENTS_ROW = 6  # nav index of the Events page


class TestEventDialog:
    def test_bare_title_sends_no_metadata(self, qapp):
        dialog = EventDialog()
        dialog.title_edit.setText("Just a title")
        values = dialog.values()
        assert values == {
            "title": "Just a title",
            "suggested_time": None,
            "priority": None,
            "project_id": None,
            "metadata": None,
        }
        client = RecordingClient()
        client.create_event(**values)
        assert client.last == (
            "POST", "/events", {"title": "Just a title"}
        )

    def test_filled_form_builds_the_metadata_block(self, qapp):
        dialog = EventDialog()
        dialog.title_edit.setText("Deep work")
        dialog.when.set_iso("2026-07-23T09:00:00")
        dialog.priority.setValue(2.0)
        dialog.duration.setValue(90)
        dialog.energy.setCurrentText("high")
        dialog.tags_edit.setText("focus, study ")
        dialog.deadline.set_iso("2026-07-24T18:00:00")
        dialog.project_edit.setText("proj_1")
        values = dialog.values()
        assert values["suggested_time"] == "2026-07-23T09:00:00"
        assert values["priority"] == 2.0
        assert values["project_id"] == "proj_1"
        assert values["metadata"] == {
            "estimated_duration_minutes": 90,
            "energy": "high",
            "tags": ["focus", "study"],
            "deadline": "2026-07-24T18:00:00",
        }

    def test_prefill_round_trips(self, qapp):
        dialog = EventDialog()
        dialog.prefill(
            {
                "description": "Old title",
                "start_time": "2026-07-22T10:00:00",
            },
            {
                "estimated_duration_minutes": 30,
                "energy": "low",
                "tags": ["a", "b"],
                "deadline": "2026-07-25T12:00:00",
            },
        )
        values = dialog.values()
        assert values["title"] == "Old title"
        assert values["suggested_time"] == "2026-07-22T10:00:00"
        assert values["metadata"]["estimated_duration_minutes"] == 30
        assert values["metadata"]["tags"] == ["a", "b"]


class TestCardBoard:
    def _client(self) -> RecordingClient:
        return RecordingClient(
            {
                ("GET", "/events"): {
                    "events": [
                        {
                            "event_id": "e1",
                            "description": "Deep work",
                            "category": "work",
                            "status": "Ready",
                            "start_time": "2026-07-21T09:00:00",
                            "end_time": None,
                            "duration_minutes": 60,
                        },
                        {
                            "event_id": "e2",
                            "description": "Groceries",
                            "category": "errand",
                            "status": "Created",
                            "start_time": "2026-07-22T17:00:00",
                            "end_time": None,
                            "duration_minutes": 30,
                        },
                        {
                            "event_id": "e3",
                            "description": "Someday idea",
                            "category": None,
                            "status": "Created",
                            "start_time": None,
                            "end_time": None,
                            "duration_minutes": None,
                        },
                    ]
                }
            }
        )

    def test_cards_group_under_date_headers(self, qapp):
        client = self._client()
        page = EventsPage(StubWindow(client))
        page.refresh(client)
        headers = [header.text() for header, _cards in page._groups]
        assert headers == ["2026-07-21", "2026-07-22", "UNSCHEDULED"]
        assert sum(len(cards) for _h, cards in page._groups) == 3

    def test_filter_hides_non_matching_cards_and_headers(self, qapp):
        client = self._client()
        page = EventsPage(StubWindow(client))
        page.refresh(client)
        page.apply_filter("deep")
        visible = [
            (header.isHidden(), [card.isHidden() for card, _s in cards])
            for header, cards in page._groups
        ]
        # Only the 07-21 group (Deep work) stays visible.
        assert visible[0] == (False, [False])
        assert visible[1] == (True, [True])
        assert visible[2] == (True, [True])
        page.apply_filter("")
        assert all(
            not card.isHidden()
            for _h, cards in page._groups
            for card, _s in cards
        )


class TestLiveAuthoring:
    def test_create_edit_duplicate_template_roundtrip(self, window, client):
        # Create with metadata: sidecar lands on the created key.
        created = client.create_event(
            "Write report",
            suggested_time="2026-07-21T10:00:00",
            metadata={"estimated_duration_minutes": 45, "energy": "high"},
        )
        assert "recommendation" in created
        key = created["event_id"] or (
            created["recommendation"]["recommendation_id"]
        )
        record = client.get_event_metadata(key)
        assert record.get("estimated_duration_minutes") == 45

        # The events page (card board) renders without a crash.
        window.navigation.setCurrentRow(EVENTS_ROW)
        page = window.current_page()
        assert isinstance(page, EventsPage)

        # Templates: save, list, instantiate, delete.
        template = client.create_template(
            "Report template", "Write report", metadata={"energy": "high"}
        )
        names = [item["name"] for item in client.list_templates()]
        assert "Report template" in names
        instantiated = client.instantiate_template(template["id"])
        assert "recommendation" in instantiated
        client.delete_template(template["id"])
        assert "Report template" not in [
            item["name"] for item in client.list_templates()
        ]

        # Recurrences: create, list, delete.
        rule = client.create_recurrence("Gym", "18:00", ["mon", "wed"])
        assert rule["time_of_day"] == "18:00"
        assert [r["id"] for r in client.list_recurrences()] == [rule["id"]]
        client.delete_recurrence(rule["id"])
        assert client.list_recurrences() == []
