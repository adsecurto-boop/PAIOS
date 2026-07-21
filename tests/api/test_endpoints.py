"""Every required endpoint, driven through the pure ApiRouter."""

import json

from tests.api.conftest import materialize_event


def ok(router, method, path, body=None):
    status, payload = router.handle(method, path, body)
    assert 200 <= status < 300, (status, payload)
    json.dumps(payload)  # every response must be JSON-serializable
    return payload


class TestSystemEndpoints:
    def test_get_status(self, router):
        payload = ok(router, "GET", "/status")
        assert payload["state"] == "Running"
        assert payload["operational"] is True
        assert payload["aggregate_counts"]["resources"] == 1

    def test_get_snapshot(self, router):
        payload = ok(router, "GET", "/snapshot")
        assert payload["current_time"] == "2026-07-21T09:00:00"
        assert payload["execution_context"] == "IdleExecutionContext"

    def test_post_tick_returns_decision_result(self, router):
        payload = ok(router, "POST", "/tick")
        assert payload["no_action"] is False
        assert payload["recommendations"][0]["reason"].startswith(
            "Energy is low"
        )


class TestRecommendationEndpoints:
    def test_list_accept_flow(self, router):
        ok(router, "POST", "/tick")
        listing = ok(router, "GET", "/recommendations")
        recommendation = listing["recommendations"][0]
        assert recommendation["status"] == "Pending"
        result = ok(
            router,
            "POST",
            f"/recommendations/{recommendation['recommendation_id']}/accept",
        )
        assert result == {"result": "accepted"}
        events = ok(router, "GET", "/events")["events"]
        assert len(events) == 1

    def test_reject_with_reason(self, router):
        ok(router, "POST", "/tick")
        listing = ok(router, "GET", "/recommendations")
        recommendation_id = listing["recommendations"][0]["recommendation_id"]
        result = ok(
            router,
            "POST",
            f"/recommendations/{recommendation_id}/reject",
            {"reason": "Feeling fine"},
        )
        assert result == {"result": "rejected"}
        assert ok(router, "GET", "/recommendations")["recommendations"] == []


class TestEventEndpoints:
    def test_get_single_event(self, router):
        event_id = materialize_event(router)
        payload = ok(router, "GET", f"/events/{event_id}")
        assert payload["event_id"] == event_id
        assert payload["status"] == "Ready"  # planned start == now -> Ready
        assert payload["transitions"][-1]["actor"]

    def test_full_lifecycle(self, router):
        event_id = materialize_event(router)
        assert ok(router, "POST", f"/events/{event_id}/start") == {
            "result": "started"
        }
        assert ok(router, "POST", f"/events/{event_id}/pause") == {
            "result": "paused"
        }
        assert ok(router, "POST", f"/events/{event_id}/resume") == {
            "result": "resumed"
        }
        assert ok(
            router,
            "POST",
            f"/events/{event_id}/complete",
            {"actual_outcome": "rested well"},
        ) == {"result": "completed"}
        payload = ok(router, "GET", f"/events/{event_id}")
        assert payload["status"] == "Completed"
        assert payload["actual_outcome"] == "rested well"

    def test_cancel(self, router):
        event_id = materialize_event(router)
        assert ok(
            router, "POST", f"/events/{event_id}/cancel", {"reason": "urgent"}
        ) == {"result": "cancelled"}
        assert ok(router, "GET", f"/events/{event_id}")["status"] == "Cancelled"


class TestGoalEndpoints:
    def test_create_and_lifecycle(self, router):
        created = router.handle(
            "POST",
            "/goals",
            {"name": "Learn Sanskrit", "description": "Read fluently"},
        )
        assert created[0] == 201
        goal = created[1]
        assert goal["accepted_by_user"] is True
        assert goal["suggested_by"] == "User"
        goal_id = goal["goal_id"]
        assert ok(router, "GET", "/goals")["goals"][0]["name"] == "Learn Sanskrit"
        assert (
            ok(router, "POST", f"/goals/{goal_id}/pause")["status"] == "Paused"
        )
        assert (
            ok(router, "POST", f"/goals/{goal_id}/resume")["status"] == "Active"
        )
        assert (
            ok(router, "POST", f"/goals/{goal_id}/complete")["status"]
            == "Completed"
        )


class TestProjectEndpoints:
    def test_create_and_progress(self, router):
        status, project = router.handle(
            "POST", "/projects", {"name": "PAIOS"}
        )
        assert status == 201
        assert project["progress"]["completion_percentage"] == 0.0
        project_id = project["project_id"]
        updated = ok(
            router,
            "POST",
            f"/projects/{project_id}/progress",
            {"completion_percentage": 40},
        )
        assert updated["progress"]["completion_percentage"] == 40.0
        listing = ok(router, "GET", "/projects")["projects"]
        assert listing[0]["progress"]["completion_percentage"] == 40.0


class TestResourceEndpoints:
    def test_create_consume_produce(self, router):
        status, resource = router.handle(
            "POST",
            "/resources",
            {"type": "focus", "current_value": 50, "unit": "points"},
        )
        assert status == 201
        resource_id = resource["resource_id"]
        assert (
            ok(
                router,
                "POST",
                f"/resources/{resource_id}/consume",
                {"amount": 20},
            )["current_value"]
            == 30.0
        )
        assert (
            ok(
                router,
                "POST",
                f"/resources/{resource_id}/produce",
                {"amount": 5},
            )["current_value"]
            == 35.0
        )
        # The seeded Energy resource plus the new Focus resource.
        assert len(ok(router, "GET", "/resources")["resources"]) == 2


class TestKnowledgeEndpoints:
    def test_create_and_list(self, router):
        status, knowledge = router.handle(
            "POST",
            "/knowledge",
            {
                "domain": "Programming",
                "topic": "Python",
                "concept": "Dataclasses",
                "confidence": 30,
            },
        )
        assert status == 201
        assert knowledge["confidence"] == 30.0
        listing = ok(router, "GET", "/knowledge")["knowledge"]
        assert listing[0]["concept"] == "Dataclasses"


class TestReflectionEndpoints:
    def test_create_after_completed_event(self, router):
        event_id = materialize_event(router)
        ok(router, "POST", f"/events/{event_id}/start")
        ok(router, "POST", f"/events/{event_id}/complete")
        status, reflection = router.handle(
            "POST",
            "/reflections",
            {
                "event_id": event_id,
                "lesson_learned": "Short rest restores focus",
                "confidence": 0.8,
            },
        )
        assert status == 201
        assert reflection["event_id"] == event_id
        assert reflection["context_window_id"]
        listing = ok(router, "GET", "/reflections")["reflections"]
        assert listing[0]["lesson_learned"] == "Short rest restores focus"


class TestDisturberEndpoint:
    def test_report_disturber(self, router):
        payload = ok(
            router,
            "POST",
            "/disturbers",
            {
                "type": "work",
                "severity": "high",
                "description": "Urgent call",
            },
        )
        assert payload["type"] == "Work"
        assert payload["severity"] == "High"
        assert payload["description"] == "Urgent call"
        # The capture chain ran; without an active window it stays
        # Analyzed evidence (the facade's documented composition).
        assert payload["state"] in ("Analyzed", "Applied")
        dashboard = ok(router, "GET", "/dashboard")
        assert any(
            d["description"] == "Urgent call"
            for d in dashboard["active_disturbers"]
        )

    def test_bad_enum_is_400(self, router):
        status, payload = router.handle(
            "POST",
            "/disturbers",
            {"type": "Alien", "severity": "High", "description": "x"},
        )
        assert status == 400
        assert "must be one of" in payload["error"]["message"]


class TestContextEndpoints:
    def test_list(self, router):
        contexts = ok(router, "GET", "/contexts")["contexts"]
        assert contexts[0]["name"] == "Office"


class TestDashboardEndpoint:
    def test_tui_parity_sections(self, router):
        payload = ok(router, "GET", "/dashboard")
        # Every TUI section is present as a JSON key.
        for key in (
            "current_time",
            "current_event",
            "current_context",
            "active_disturbers",
            "recommendations",
            "goals",
            "projects",
            "today",
            "health",
            "learning",
            "system",
        ):
            assert key in payload, key
        assert payload["current_time"] == "2026-07-21T09:00:00"
        assert payload["current_event"] is None
        assert payload["current_context"]["execution_context"] == (
            "IdleExecutionContext"
        )
        assert payload["health"]["resources"][0]["type"] == "Energy"
        assert payload["system"]["scheduler"] == "Idle"
        assert payload["system"]["kernel"] == "Running"

    def test_dashboard_reflects_running_event(self, router):
        event_id = materialize_event(router)
        ok(router, "POST", f"/events/{event_id}/start")
        payload = ok(router, "GET", "/dashboard")
        assert payload["current_event"]["event_id"] == event_id
        assert payload["current_event"]["status"] == "Started"
        assert payload["current_event"]["started_at"] == "2026-07-21T09:00:00"
        assert payload["today"]["running"][0]["event_id"] == event_id
