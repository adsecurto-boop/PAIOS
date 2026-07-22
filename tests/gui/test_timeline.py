"""Timeline bucketing: a pure function of (entries, events, now, view).

The fixed 'now' is passed explicitly — no clocks are read — so the
today/tomorrow/overdue maths is deterministic.
"""

from datetime import datetime

from paios_gui.timeline_page import TimelinePage, bucket_plan

from tests.gui.test_client_m20 import RecordingClient
from tests.gui.test_planning_page import StubWindow

NOW = datetime(2026, 7, 21, 9, 0, 0)


def entry(event_id, start, end, duration=60):
    return {
        "event_id": event_id,
        "planned_start": start,
        "planned_end": end,
        "duration_minutes": duration,
        "priority": 1.0,
        "recommendation_id": None,
    }


def event(event_id, status, start=None, end=None, duration=None):
    return {
        "event_id": event_id,
        "description": f"Event {event_id}",
        "category": None,
        "status": status,
        "start_time": start,
        "end_time": end,
        "duration_minutes": duration,
    }


ENTRIES = [
    entry("e1", "2026-07-21T10:00:00", "2026-07-21T11:00:00"),
    entry("e2", "2026-07-21T13:00:00", "2026-07-21T14:00:00"),
    entry("e3", "2026-07-22T09:00:00", "2026-07-22T10:00:00"),
    entry("e4", "2026-07-21T07:00:00", "2026-07-21T08:00:00"),  # past
]
EVENTS = [
    event("e1", "Created"),
    event("e2", "Created"),
    event("e3", "Created"),
    event("e4", "Created"),
    event(
        "run", "Started",
        start="2026-07-21T08:30:00", duration=60,
    ),
    event(
        "done", "Completed",
        start="2026-07-21T07:00:00", end="2026-07-21T08:00:00",
    ),
    event("rdy", "Ready"),
    event(
        "old", "Completed",
        start="2026-07-20T07:00:00", end="2026-07-20T08:00:00",
    ),
]


def ids(rows):
    return [
        (row["entry"] or row["event"])["event_id"] for row in rows
    ]


class TestBuckets:
    def test_today_view(self):
        buckets = bucket_plan(ENTRIES, EVENTS, NOW, "Today")
        assert ids(buckets["current"]) == ["run"]
        assert ids(buckets["completed_today"]) == ["done"]  # not "old"
        assert ids(buckets["ready"]) == ["rdy"]
        assert ids(buckets["overdue"]) == ["e4"]
        assert ids(buckets["up_next"]) == ["e1"]
        assert ids(buckets["upcoming"]) == ["e2"]  # e3 is tomorrow

    def test_tomorrow_view(self):
        buckets = bucket_plan(ENTRIES, EVENTS, NOW, "Tomorrow")
        assert ids(buckets["up_next"]) == ["e3"]
        assert buckets["upcoming"] == []
        assert ids(buckets["overdue"]) == ["e4"]  # overdue is viewless

    def test_week_and_agenda_views(self):
        for view in ("Week", "Agenda"):
            buckets = bucket_plan(ENTRIES, EVENTS, NOW, view)
            assert ids(buckets["up_next"]) == ["e1"]
            assert ids(buckets["upcoming"]) == ["e2", "e3"]

    def test_running_event_never_reappears_as_upcoming(self):
        entries = [
            entry("run", "2026-07-21T10:30:00", "2026-07-21T11:30:00")
        ]
        buckets = bucket_plan(entries, EVENTS, NOW, "Today")
        assert ids(buckets["current"]) == ["run"]
        assert buckets["up_next"] == []

    def test_terminal_event_never_goes_overdue(self):
        entries = [
            entry("done", "2026-07-21T05:00:00", "2026-07-21T06:00:00")
        ]
        buckets = bucket_plan(entries, EVENTS, NOW, "Today")
        assert buckets["overdue"] == []


class TestPageRendering:
    def test_render_fills_now_and_countdown(self, qapp):
        page = TimelinePage(StubWindow(RecordingClient()))
        page.render(
            {"created_at": None, "entries": ENTRIES},
            EVENTS,
            NOW.isoformat(),
        )
        assert page.countdown_label.text().startswith("Up next in")
        # NOW shows the running event with its elapsed progress bar.
        assert page._now_rows, "the NOW card must show the running event"
        assert page.empty_label.isHidden()

    def test_render_idle_state(self, qapp):
        page = TimelinePage(StubWindow(RecordingClient()))
        page.render({"created_at": None, "entries": []}, [], NOW.isoformat())
        assert page.countdown_label.text() == "Nothing scheduled next."
        assert not page.empty_label.isHidden()

    def test_refresh_pulls_plan_events_dashboard(self, qapp):
        client = RecordingClient(
            {
                ("GET", "/plan"): {"created_at": None, "entries": []},
                ("GET", "/events"): {"events": []},
                ("GET", "/dashboard"): {
                    "current_time": NOW.isoformat()
                },
            }
        )
        page = TimelinePage(StubWindow(client))
        page.refresh(client)
        paths = [path for _method, path, _body in client.calls]
        assert paths == ["/plan", "/events", "/dashboard"]
