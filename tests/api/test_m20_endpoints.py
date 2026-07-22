"""M20 REST additions: events CRUD-composition, plan, planning stores,
assistant (offline deterministic path), backups."""

import pytest

from paios.api import assistant_support
from paios.api.routes import ApiRouter
from paios.planning.service import PlanningService
from paios.system.backup import BackupManager


@pytest.fixture
def full_router(api_app, tmp_path):
    """Router with the M20 collaborators composed (assistant absent ->
    deterministic fallbacks must answer)."""
    return ApiRouter(
        api_app,
        planning=PlanningService(tmp_path / "planning-data"),
        backups=BackupManager(
            tmp_path / "data", tmp_path / "backups"
        ),
    )


def ok(router, method, path, body=None, expect=200):
    status, payload = router.handle(method, path, body)
    assert status == expect, payload
    return payload


class TestEventCreation:
    def test_post_events_creates_scheduled_event(self, full_router):
        payload = ok(
            full_router, "POST", "/events",
            {"title": "Buy medicine", "priority": 2.0,
             "metadata": {"tags": ["errand"], "energy": "low"}},
            expect=201,
        )
        assert payload["materialized"] is True
        event_id = payload["event_id"]
        event = ok(full_router, "GET", f"/events/{event_id}")
        assert event["description"] == "Buy medicine"
        # Due-now intents are promoted Scheduled -> Ready by the
        # Scheduler's own advance step; both prove materialization.
        assert event["status"] in ("Scheduled", "Ready")
        metadata = ok(full_router, "GET", f"/events/{event_id}/metadata")
        assert metadata["tags"] == ["errand"]
        assert metadata["energy"] == "low"

    def test_post_events_mode_now_reports_spontaneous_action(
        self, full_router
    ):
        payload = ok(
            full_router, "POST", "/events",
            {"title": "Took a call", "mode": "now"}, expect=201,
        )
        assert payload["description"] == "Took a call"

    def test_post_events_requires_title(self, full_router):
        status, payload = full_router.handle("POST", "/events", {})
        assert status == 400
        assert "title" in payload["error"]["message"]

    def test_bad_mode_rejected(self, full_router):
        status, _ = full_router.handle(
            "POST", "/events", {"title": "X", "mode": "someday"}
        )
        assert status == 400


class TestEventEditDuplicateMetadata:
    def test_put_event_supersedes_original(self, full_router):
        created = ok(
            full_router, "POST", "/events", {"title": "Gym"}, expect=201
        )
        edited = ok(
            full_router, "PUT", f"/events/{created['event_id']}",
            {"title": "Gym: legs day"},
        )
        assert edited["event_id"] != created["event_id"]
        original = ok(full_router, "GET", f"/events/{created['event_id']}")
        assert original["status"] == "Cancelled"

    def test_put_event_relinks_metadata(self, full_router):
        created = ok(
            full_router, "POST", "/events",
            {"title": "Gym", "metadata": {"tags": ["fitness"]}},
            expect=201,
        )
        edited = ok(
            full_router, "PUT", f"/events/{created['event_id']}",
            {"title": "Gym v2"},
        )
        moved = ok(
            full_router, "GET", f"/events/{edited['event_id']}/metadata"
        )
        assert moved["tags"] == ["fitness"]

    def test_duplicate_copies_metadata(self, full_router):
        created = ok(
            full_router, "POST", "/events",
            {"title": "Temple", "metadata": {"energy": "low"}}, expect=201,
        )
        copy = ok(
            full_router, "POST",
            f"/events/{created['event_id']}/duplicate", {}, expect=201,
        )
        copied_meta = ok(
            full_router, "GET", f"/events/{copy['event_id']}/metadata"
        )
        assert copied_meta["energy"] == "low"

    def test_put_metadata_validates(self, full_router):
        created = ok(
            full_router, "POST", "/events", {"title": "X"}, expect=201
        )
        status, payload = full_router.handle(
            "PUT", f"/events/{created['event_id']}/metadata",
            {"energy": "extreme"},
        )
        assert status == 400, payload


class TestPlanEndpoint:
    def test_plan_lists_scheduled_intents_in_order(self, full_router):
        ok(full_router, "POST", "/events", {"title": "A"}, expect=201)
        ok(full_router, "POST", "/events", {"title": "B"}, expect=201)
        plan = ok(full_router, "GET", "/plan")
        assert len(plan["entries"]) >= 2
        starts = [entry["planned_start"] for entry in plan["entries"]]
        assert starts == sorted(starts)
        assert all(
            entry["planned_end"] > entry["planned_start"]
            for entry in plan["entries"]
        )


class TestTemplatesAndRecurrences:
    def test_template_crud_and_instantiate(self, full_router):
        template = ok(
            full_router, "POST", "/templates",
            {"name": "Gym", "title": "Gym session",
             "metadata": {"energy": "high"}},
            expect=201,
        )
        listed = ok(full_router, "GET", "/templates")
        assert [item["id"] for item in listed["templates"]] == [
            template["id"]
        ]
        instantiated = ok(
            full_router, "POST",
            f"/templates/{template['id']}/instantiate", {}, expect=201,
        )
        assert instantiated["materialized"] is True
        metadata = ok(
            full_router, "GET",
            f"/events/{instantiated['event_id']}/metadata",
        )
        assert metadata["energy"] == "high"
        ok(full_router, "DELETE", f"/templates/{template['id']}")
        assert ok(full_router, "GET", "/templates")["templates"] == []

    def test_recurrence_crud_and_tick_expansion(self, full_router):
        rule = ok(
            full_router, "POST", "/recurrences",
            {"title": "Temple", "time_of_day": "07:30", "days": ["sun"],
             "first_run": "2026-07-19T07:30:00"},
            expect=201,
        )
        tick = ok(full_router, "POST", "/tick")
        assert tick["recurrences_expanded"] == 1
        events = ok(full_router, "GET", "/events")["events"]
        assert any(
            event["description"] == "Temple" for event in events
        )
        advanced = ok(full_router, "GET", "/recurrences")["recurrences"][0]
        assert advanced["next_run"] > rule["next_run"]
        # Same tick again: nothing due anymore.
        assert ok(full_router, "POST", "/tick")[
            "recurrences_expanded"
        ] == 0
        ok(full_router, "DELETE", f"/recurrences/{rule['id']}")

    def test_unknown_template_404(self, full_router):
        status, _ = full_router.handle(
            "POST", "/templates/tpl_missing/instantiate", {}
        )
        assert status == 404


class TestInbox:
    def test_capture_convert_archive_delete(self, full_router):
        item = ok(
            full_router, "POST", "/inbox", {"text": "Need haircut"},
            expect=201,
        )
        second = ok(
            full_router, "POST", "/inbox", {"text": "Read chapter 3"},
            expect=201,
        )
        converted = ok(
            full_router, "POST", f"/inbox/{item['id']}/convert",
            {"to": "event"},
        )
        assert converted["item"]["status"] == "converted"
        assert converted["item"]["converted_to"].startswith("event:")
        assert converted["created"]["materialized"] is True
        archived = ok(
            full_router, "POST", f"/inbox/{second['id']}/archive", {}
        )
        assert archived["status"] == "archived"
        ok(full_router, "DELETE", f"/inbox/{item['id']}")
        remaining = ok(full_router, "GET", "/inbox")["items"]
        assert [entry["id"] for entry in remaining] == [second["id"]]

    def test_convert_to_goal_and_project(self, full_router):
        for target, key in (("goal", "goal_id"), ("project", "project_id")):
            item = ok(
                full_router, "POST", "/inbox",
                {"text": f"Become {target}"}, expect=201,
            )
            converted = ok(
                full_router, "POST", f"/inbox/{item['id']}/convert",
                {"to": target},
            )
            assert key in converted["created"]

    def test_bad_convert_target_rejected(self, full_router):
        item = ok(
            full_router, "POST", "/inbox", {"text": "X"}, expect=201
        )
        status, _ = full_router.handle(
            "POST", f"/inbox/{item['id']}/convert", {"to": "habit"}
        )
        assert status == 400


class TestAssistantOffline:
    def test_status_reports_heuristic_fallback(self, full_router):
        payload = ok(full_router, "GET", "/assistant/status")
        assert payload["provider"] == "none"
        assert payload["available"] is False
        assert payload["fallback"] == "heuristic"
        # The reason is a user-facing sentence explaining how to enable
        # a real provider (M20 polish: no silent fallback).
        assert "no AI provider configured" in payload["reason"]
        assert "PAIOS_AI_PROVIDER" in payload["reason"]

    def test_compose_none_explains_how_to_configure(self, monkeypatch):
        monkeypatch.delenv("PAIOS_AI_PROVIDER", raising=False)
        provider, orchestrator, reason = (
            assistant_support.compose_assistant("none")
        )
        assert provider == "none"
        assert orchestrator is None
        assert "PAIOS_AI_PROVIDER" in reason

    def test_compose_env_variable_overrides_config(self, monkeypatch):
        monkeypatch.setenv("PAIOS_AI_PROVIDER", "null")
        provider, orchestrator, reason = (
            assistant_support.compose_assistant("none")
        )
        assert provider == "null"
        assert orchestrator is not None
        assert "ready" in reason

    def test_compose_missing_sdk_or_key_stays_graceful(self, monkeypatch):
        # Whichever is absent (SDK or OPENAI_API_KEY), composition must
        # return None with an actionable reason — never raise.
        monkeypatch.setenv("PAIOS_AI_PROVIDER", "openai")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        provider, orchestrator, reason = (
            assistant_support.compose_assistant("none")
        )
        assert provider == "openai"
        assert orchestrator is None
        assert "openai" in reason.lower()

    def test_plan_proposal_is_deterministic_offline(self, full_router):
        body = {"text": "Tomorrow\nTemple\nGym\nBuild PAIOS"}
        first = ok(full_router, "POST", "/assistant/plan", body)
        second = ok(full_router, "POST", "/assistant/plan", body)
        assert first == second
        assert first["source"] == "heuristic"
        kinds = {item["title"]: item["kind"] for item in first["items"]}
        assert kinds["Temple"] == "event"
        assert kinds["Build PAIOS"] == "project"
        assert all(
            item["day_scope"] == "tomorrow" for item in first["items"]
        )

    def test_plan_detects_duplicates_of_existing_work(self, full_router):
        ok(full_router, "POST", "/events", {"title": "Gym"}, expect=201)
        proposal = ok(
            full_router, "POST", "/assistant/plan", {"text": "Gym"}
        )
        assert proposal["items"][0]["duplicate_of"] == "Gym"

    def test_explain_day_grounds_reasons_in_facts(self, full_router):
        created = ok(
            full_router, "POST", "/events",
            {"title": "Deep work",
             "metadata": {"energy": "high",
                          "deadline": "2026-07-23T17:00:00"}},
            expect=201,
        )
        payload = ok(full_router, "POST", "/assistant/explain-day", {})
        assert payload["source"] == "deterministic"
        entry = next(
            item
            for item in payload["entries"]
            if item["event_id"] == created["event_id"]
        )
        assert "high energy" in entry["reason"]
        assert "deadline" in entry["reason"]


class TestBackups:
    def test_create_list_backups(self, full_router):
        assert ok(full_router, "GET", "/backups")["backups"] == []
        created = ok(full_router, "POST", "/backups", {}, expect=201)
        listed = ok(full_router, "GET", "/backups")["backups"]
        assert [item["name"] for item in listed] == [created["name"]]

    def test_restore_requires_archive_field(self, full_router):
        status, _ = full_router.handle("POST", "/backups/restore", {})
        assert status == 400


class TestCompositionGuards:
    def test_planning_routes_unavailable_without_composition(self, api_app):
        bare = ApiRouter(api_app)
        status, payload = bare.handle("GET", "/inbox")
        assert status == 503, payload

    def test_plan_and_events_post_work_without_planning(self, api_app):
        bare = ApiRouter(api_app)
        created_status, created = bare.handle(
            "POST", "/events", {"title": "No planning composed"}
        )
        assert created_status == 201, created
        plan_status, plan = bare.handle("GET", "/plan")
        assert plan_status == 200 and plan["entries"], plan
