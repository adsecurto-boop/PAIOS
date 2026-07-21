"""REST integration: the GUI's ApiClient against a live ApiServer."""

import pytest

from paios_gui import ApiClient, ApiResponseError, ApiUnreachable

from tests.gui.conftest import unreachable_client


def drive_event_via_rest(client: ApiClient) -> str:
    """Tick -> accept the recommendation -> return the created event id."""
    client._request("POST", "/tick", {})
    recommendations = client.get_recommendations()
    assert recommendations, "seeded scenario must recommend rest"
    client.accept_recommendation(recommendations[0]["recommendation_id"])
    events = client.get_events()
    assert events
    return events[0]["event_id"]


class TestReads:
    def test_dashboard_resources_reflections(self, client):
        dashboard = client.get_dashboard()
        assert set(dashboard) >= {
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
        }
        assert isinstance(client.get_resources(), list)
        assert isinstance(client.get_reflections(), list)
        assert isinstance(client.get_knowledge(), list)

    def test_status(self, client):
        assert client.get_status()["operational"] is True


class TestActions:
    def test_goal_project_progress(self, client):
        goal = client.create_goal("Learn Qt", "GUI milestone")
        assert goal["name"] == "Learn Qt"
        project = client.create_project("Desktop app", "M13")
        updated = client.update_progress(project["project_id"], 40.0)
        assert updated["progress"]["completion_percentage"] == 40.0

    def test_event_lifecycle_and_reflection(self, client):
        event_id = drive_event_via_rest(client)
        client.start_event(event_id)
        client.pause_event(event_id)
        client.resume_event(event_id)
        client.complete_event(event_id, actual_outcome="rested")
        reflection = client.create_reflection(
            event_id, lesson_learned="breaks work", confidence=0.8
        )
        assert reflection["event_id"] == event_id

    def test_reject_recommendation(self, client):
        client._request("POST", "/tick", {})
        recommendations = client.get_recommendations()
        client.reject_recommendation(
            recommendations[0]["recommendation_id"], reason="busy"
        )
        remaining_ids = [
            r["recommendation_id"] for r in client.get_recommendations()
        ]
        assert recommendations[0]["recommendation_id"] not in remaining_ids

    def test_report_disturber(self, client):
        disturber = client.report_disturber(
            type="Work", severity="High", description="Urgent call"
        )
        assert disturber["type"] == "Work"
        assert disturber["severity"] == "High"
        assert disturber["state"] in ("Analyzed", "Applied")


class TestErrors:
    def test_validation_error_carries_api_payload(self, client):
        with pytest.raises(ApiResponseError) as excinfo:
            client.create_goal("")
        assert excinfo.value.status == 400
        assert excinfo.value.error_type == "ApiError"

    def test_unknown_entity_is_404(self, client):
        with pytest.raises(ApiResponseError) as excinfo:
            client.update_progress("no-such-project", 10.0)
        assert excinfo.value.status == 404
        assert excinfo.value.error_type == "EntityNotFound"

    def test_runtime_refusal_is_500_with_message(self, client):
        # Unknown event ids die inside the Runtime; M12 maps unimportable
        # runtime errors to 500 with the name preserved.
        with pytest.raises(ApiResponseError) as excinfo:
            client.start_event("no-such-event")
        assert excinfo.value.status == 500
        assert "Runtime State" in str(excinfo.value)

    def test_unreachable_server(self):
        with pytest.raises(ApiUnreachable):
            unreachable_client().get_dashboard()
