"""Quick Capture: instant capture, AI-suggested kind chips, convert /
archive / delete flows. Fake client pins the calls; the live server
proves the full round trip.
"""

from paios_gui import inbox_page as inbox_module
from paios_gui.inbox_page import InboxPage

from tests.gui.test_client_m20 import RecordingClient
from tests.gui.test_planning_page import StubWindow

INBOX_ROW = 2  # nav index of the Inbox page


def suggesting_client() -> RecordingClient:
    return RecordingClient(
        {
            ("GET", "/inbox"): {
                "items": [
                    {
                        "id": "i1",
                        "text": "Buy milk",
                        "status": "open",
                        "created_at": "2026-07-21T08:00:00",
                        "converted_to": None,
                    },
                    {
                        "id": "i2",
                        "text": "Old note",
                        "status": "archived",
                        "created_at": "2026-07-20T08:00:00",
                        "converted_to": None,
                    },
                ]
            },
            ("POST", "/assistant/plan"): {
                "items": [{"text": "Buy milk", "kind": "event"}]
            },
        }
    )


class TestSuggestions:
    def test_open_items_get_a_suggested_chip(self, qapp):
        client = suggesting_client()
        page = InboxPage(StubWindow(client))
        page.refresh(client)
        assert page.cells(page._rows[0])[2] == "Suggested: Event"
        assert page.cells(page._rows[1])[2] == "—"  # archived: no chip
        # The classification request carried the open texts only.
        plan_calls = [
            call for call in client.calls if call[1] == "/assistant/plan"
        ]
        assert plan_calls == [
            ("POST", "/assistant/plan", {"text": "Buy milk"})
        ]

    def test_convert_as_suggested_is_one_click(self, qapp):
        client = suggesting_client()
        page = InboxPage(StubWindow(client))
        page.refresh(client)
        button = page.table.cellWidget(0, len(page.columns) - 1)
        assert button is not None, "open+suggested row offers the button"
        assert page.table.cellWidget(1, len(page.columns) - 1) is None
        button.click()
        assert ("POST", "/inbox/i1/convert", {"to": "event"}) in (
            client.calls
        )

    def test_suggestion_failure_degrades_to_no_chips(self, qapp):
        client = suggesting_client()

        def boom(text):
            raise RuntimeError("assistant down")

        client.assistant_plan = boom
        page = InboxPage(StubWindow(client))
        page.refresh(client)
        assert page.cells(page._rows[0])[2] == "—"


class TestLiveFlow:
    def test_capture_convert_archive_delete(
        self, window, client, monkeypatch
    ):
        window.navigation.setCurrentRow(INBOX_ROW)
        page = window.current_page()
        assert isinstance(page, InboxPage)

        # Capture: Enter-equivalent handler adds and clears.
        page.capture_edit.setText("Read DDD chapter")
        page._on_add()
        assert page.capture_edit.text() == ""
        page.refresh(client)
        texts = [row["text"] for row in page._rows]
        assert "Read DDD chapter" in texts
        item = next(
            row for row in page._rows
            if row["text"] == "Read DDD chapter"
        )

        # Convert to goal: the item flips to converted, the goal exists.
        result = client.convert_inbox(
            item["id"], "goal", title="Read DDD"
        )
        assert result["item"]["status"] == "converted"
        assert result["created"]["name"] == "Read DDD"
        assert any(
            goal["name"] == "Read DDD" for goal in client.get_goals()
        )

        # Archive a second capture.
        page.capture_edit.setText("Another thought")
        page._on_add()
        page.refresh(client)
        second = next(
            row for row in page._rows
            if row["text"] == "Another thought"
        )
        page.table.setCurrentCell(
            page._rows.index(second), 0
        )
        page._on_archive()
        page.refresh(client)
        second = next(
            row for row in page._rows
            if row["text"] == "Another thought"
        )
        assert second["status"] == "archived"

        # Delete it (confirm dialog answered yes via monkeypatch).
        monkeypatch.setattr(
            inbox_module, "confirm", lambda *args, **kwargs: True
        )
        page.table.setCurrentCell(page._rows.index(second), 0)
        page._on_delete()
        page.refresh(client)
        assert "Another thought" not in [
            row["text"] for row in page._rows
        ]
