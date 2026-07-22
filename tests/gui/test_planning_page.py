"""Planning page: the Today Home header (greeting, Today's Focus,
Next-with-reasons) and the proposal-cards -> approve flow. Fake client —
these tests pin which REST calls the page makes and what it renders,
not what the server decides.
"""

from datetime import datetime

from paios_gui.planning_page import PlanningPage, greeting

from tests.gui.test_client_m20 import RecordingClient


class StubWindow:
    """The minimal window surface a page touches."""

    def __init__(self, client) -> None:
        self.client = client
        self.notices: list[tuple[str, str]] = []

    def notify(self, text: str, kind: str = "info") -> None:
        self.notices.append((kind, text))

    def refresh_now(self) -> None:
        pass

    def run_action(self, call, notice: str) -> None:
        call()
        self.notices.append(("ok", notice))


def proposal() -> dict:
    return {
        "source": "heuristic",
        "items": [
            {
                "text": "Learn Rust",
                "kind": "goal",
                "title": "Learn Rust",
                "duplicate_of": None,
                "notes": None,
            },
            {
                "text": "Temple",
                "kind": "event",
                "title": "Temple",
                "duplicate_of": None,
                "notes": "similar to: Temple visit",
            },
            {
                "text": "Existing thing",
                "kind": "event",
                "title": "Existing thing",
                "duplicate_of": "Existing thing",
                "notes": None,
            },
        ],
        "questions": ["When should Temple happen?"],
        "confidence": 0.5,
    }


NOW_ISO = "2026-07-21T09:00:00"


def home_plan() -> dict:
    return {
        "created_at": NOW_ISO,
        "entries": [
            {
                "event_id": "e1",
                "planned_start": "2026-07-21T09:40:00",
                "planned_end": "2026-07-21T10:40:00",
                "duration_minutes": 60,
                "priority": 3.0,
                "recommendation_id": None,
            },
            {
                "event_id": "e2",
                "planned_start": "2026-07-21T13:00:00",
                "planned_end": "2026-07-21T14:00:00",
                "duration_minutes": 60,
                "priority": 1.0,
                "recommendation_id": None,
            },
        ],
    }


def home_events(running: bool = False) -> list[dict]:
    events = [
        {
            "event_id": "e1",
            "description": "Deep work",
            "status": "Created",
            "start_time": None,
            "end_time": None,
            "duration_minutes": 60,
        },
        {
            "event_id": "e2",
            "description": "Groceries",
            "status": "Created",
            "start_time": None,
            "end_time": None,
            "duration_minutes": 60,
        },
    ]
    if running:
        events.append(
            {
                "event_id": "run",
                "description": "Writing report",
                "status": "Started",
                "start_time": "2026-07-21T08:30:00",
                "end_time": None,
                "duration_minutes": 60,
            }
        )
    return events


class TestGreeting:
    def test_wording_follows_the_injected_hour(self):
        assert greeting(datetime(2026, 7, 21, 8, 0)) == "Good Morning."
        assert greeting(datetime(2026, 7, 21, 11, 59)) == "Good Morning."
        assert greeting(datetime(2026, 7, 21, 12, 0)) == "Good Afternoon."
        assert greeting(datetime(2026, 7, 21, 17, 59)) == "Good Afternoon."
        assert greeting(datetime(2026, 7, 21, 18, 0)) == "Good Evening."
        assert greeting(datetime(2026, 7, 21, 23, 30)) == "Good Evening."

    def test_header_label_uses_injected_local_now(self, qapp):
        page = PlanningPage(StubWindow(RecordingClient()))
        page.update_home(
            home_plan(),
            home_events(),
            NOW_ISO,
            local_now=datetime(2026, 7, 21, 20, 0),
        )
        assert page.greeting_label.text() == "Good Evening."


class TestTodaysFocus:
    def test_running_event_shows_elapsed_progress(self, qapp):
        page = PlanningPage(StubWindow(RecordingClient()))
        page.update_home(home_plan(), home_events(running=True), NOW_ISO)
        assert page.focus_label.text() == "Writing report"
        assert page.focus_progress.isHidden() is False
        assert page.focus_progress.value() == 50  # 30 of 60 minutes
        assert page.focus_countdown.isHidden() is True
        # Next line falls to the first planned entry.
        assert "Deep work" in page.next_label.text()

    def test_no_running_event_counts_down_to_next_planned(self, qapp):
        page = PlanningPage(StubWindow(RecordingClient()))
        page.update_home(home_plan(), home_events(), NOW_ISO)
        assert page.focus_label.text() == "Deep work —"
        assert page.focus_countdown.isHidden() is False
        assert "starts in 40 minute" in page.focus_countdown.text()
        assert page.focus_progress.isHidden() is True
        assert "Next: 13:00  Groceries" in page.next_label.text()

    def test_empty_plan_invites_planning_below(self, qapp):
        page = PlanningPage(StubWindow(RecordingClient()))
        page.update_home({"created_at": None, "entries": []}, [], NOW_ISO)
        assert (
            "Nothing scheduled yet — plan your day below."
            in page.focus_label.text()
        )
        assert page.next_label.isHidden()
        assert page.next_reasons.isHidden()


class TestNextReasons:
    def test_reason_string_splits_into_bullets(self, qapp):
        page = PlanningPage(StubWindow(RecordingClient()))
        page.update_home(
            home_plan(),
            home_events(),
            NOW_ISO,
            explanation={
                "source": "deterministic",
                "entries": [
                    {
                        "event_id": "e2",
                        "title": "Groceries",
                        "reason": (
                            "priority 1.0; deadline 2026-07-21;"
                            " energy low"
                        ),
                    }
                ],
            },
        )
        text = page.next_reasons.text()
        assert page.next_reasons.isHidden() is False
        assert text.startswith("Recommended because:")
        assert text.count("•") == 3
        assert "deadline 2026-07-21" in text

    def test_no_recorded_reason_hides_the_bullets(self, qapp):
        page = PlanningPage(StubWindow(RecordingClient()))
        page.update_home(home_plan(), home_events(), NOW_ISO)
        assert page.next_reasons.isHidden()


class TestProposalCards:
    def test_cards_render_and_duplicates_start_unchecked(self, qapp):
        page = PlanningPage(StubWindow(RecordingClient()))
        page.show_proposal(proposal())
        assert len(page.cards) == 3
        assert page.cards[0].include.isChecked() is True
        assert page.cards[1].include.isChecked() is True
        assert page.cards[2].include.isChecked() is False  # duplicate
        assert page.cards[0].kind_box.currentText() == "goal"
        assert page.cards[1].kind_box.currentText() == "event"

    def test_question_attaches_to_its_card(self, qapp):
        page = PlanningPage(StubWindow(RecordingClient()))
        page.show_proposal(proposal())
        assert page.cards[1].question_label is not None
        assert "Temple" in page.cards[1].question_label.text()
        assert page.questions_label.isHidden()  # nothing unattached

    def test_unmatched_question_lands_below_cards(self, qapp):
        page = PlanningPage(StubWindow(RecordingClient()))
        data = proposal()
        data["questions"] = ["Which day did you mean?"]
        page.show_proposal(data)
        assert not page.questions_label.isHidden()
        assert "Which day" in page.questions_label.text()


class TestApply:
    def test_apply_executes_only_checked_cards(self, qapp):
        client = RecordingClient()
        page = PlanningPage(StubWindow(client))
        page.show_proposal(proposal())
        # Duration and priority on the event card travel as body +
        # metadata; the duplicate stays unchecked and must not fire.
        page.cards[1].priority.setValue(2.0)
        page.cards[1].duration.setValue(45)
        page.apply()
        assert client.calls == [
            (
                "POST",
                "/goals",
                {"name": "Learn Rust", "description": ""},
            ),
            (
                "POST",
                "/events",
                {
                    "title": "Temple",
                    "priority": 2.0,
                    "metadata": {"estimated_duration_minutes": 45},
                },
            ),
        ]
        assert "Applied 2 item(s)." in page.summary_label.text()

    def test_kind_override_changes_the_endpoint(self, qapp):
        client = RecordingClient()
        page = PlanningPage(StubWindow(client))
        page.show_proposal(proposal())
        page.cards[0].kind_box.setCurrentText("inbox")
        page.cards[1].include.setChecked(False)
        page.apply()
        assert client.calls == [
            ("POST", "/inbox", {"text": "Learn Rust"}),
        ]


class TestExplainAndReview:
    def test_explanation_cards_show_time_title_reason(self, qapp):
        page = PlanningPage(StubWindow(RecordingClient()))
        page.show_explanation(
            {
                "source": "deterministic",
                "entries": [
                    {
                        "event_id": "e1",
                        "title": "Deep work",
                        "planned_start": "2026-07-21T09:00:00",
                        "duration_minutes": 60,
                        "reason": "priority 3.0; deadline today",
                    }
                ],
            }
        )
        assert len(page.cards) == 1
        assert "Today's plan: 1 entry" in page.summary_label.text()

    def test_review_today_composes_three_groups(self, qapp):
        page = PlanningPage(StubWindow(RecordingClient()))
        events = [
            {
                "event_id": "done",
                "description": "Morning run",
                "status": "Completed",
                "start_time": "2026-07-21T07:00:00",
                "end_time": "2026-07-21T08:00:00",
            },
            {
                "event_id": "late",
                "description": "Report",
                "status": "Created",
                "start_time": "2026-07-21T09:00:00",
                "end_time": None,
            },
            {
                "event_id": "next",
                "description": "Gym",
                "status": "Created",
                "start_time": "2026-07-21T18:00:00",
                "end_time": None,
            },
        ]
        page.show_review(
            {"current_time": "2026-07-21T12:00:00"}, events
        )
        assert len(page.cards) == 3
        assert (
            "1 done, 1 overdue, 1 still to come"
            in page.summary_label.text()
        )


class TestProposeOverRest:
    def test_propose_against_live_heuristic(self, window):
        """The real endpoint answers; the page renders cards from it."""
        page = window.planning
        page.capture.setPlainText("Tomorrow\nTemple\nStudy ISTQB")
        page.propose()
        assert page.cards, "heuristic proposal must yield cards"
        assert any(
            "Proposal ready" in text
            for text in window.dashboard.notice_log.notices()
        )
