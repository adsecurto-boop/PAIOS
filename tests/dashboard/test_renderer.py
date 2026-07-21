"""Renderer over a real application: every section, live data, and the
strict facade-query-only delegation contract."""

from paios.dashboard import DashboardConfig
from paios.dashboard.layout import SECTION_ORDER
from paios.dashboard.renderer import DashboardRenderer

from tests.application.conftest import USER
from tests.application.test_use_cases import tick_and_get_rest_recommendation
from tests.dashboard.conftest import ALLOWED_QUERIES


def frame_of(application) -> str:
    return DashboardRenderer(application).render()


class TestFrameStructure:
    def test_every_mission_section_present_in_order(self, dash_app):
        frame = frame_of(dash_app)
        positions = [frame.index(title) for title in SECTION_ORDER]
        assert positions == sorted(positions)
        assert "PAIOS DASHBOARD" in frame
        assert "Current Time:  2026-07-21 09:00:00" in frame

    def test_daemon_not_attached_by_default(self, dash_app):
        assert "Not attached" in frame_of(dash_app)

    def test_attached_daemon_is_reported(self, dash_app):
        from types import SimpleNamespace

        daemon = SimpleNamespace(
            state=SimpleNamespace(value="Running"),
            tick_count=7,
            last_tick_at=None,
        )
        frame = DashboardRenderer(dash_app, daemon=daemon).render()
        assert "Running — 7 tick(s)" in frame


class TestSections:
    def test_idle_state_reads_honestly(self, dash_app):
        frame = frame_of(dash_app)
        assert "No running event." in frame
        assert "IdleExecutionContext" in frame
        assert "Active Disturbers: none" in frame
        assert "No active recommendations." in frame
        assert "No goals." in frame
        assert "No projects." in frame

    def test_running_event_shows_duration_and_remaining(self, dash_app):
        recommendation = tick_and_get_rest_recommendation(dash_app)
        dash_app.accept_recommendation(recommendation.recommendation_id)
        event = dash_app.list_events()[0]
        dash_app.start_event(event.event_id)
        frame = frame_of(dash_app)
        assert "[Started]" in frame
        # Timing comes from lifecycle evidence (the Started transition).
        assert "Started:   2026-07-21 09:00:00" in frame
        assert "Duration:  0m" in frame
        assert "Remaining: -" in frame  # rest events carry no Duration
        assert "Running:   1" in frame

    def test_recommendations_listed_numbered(self, dash_app):
        dash_app.tick()
        frame = frame_of(dash_app)
        assert "1. (8.5) Energy is low" in frame

    def test_goals_projects_and_progress_bar(self, dash_app):
        dash_app.add_goal(USER, "Learn Sanskrit")
        project = dash_app.add_project(USER, "PAIOS")
        dash_app.update_project_progress(project.project_id, 40.0)
        frame = frame_of(dash_app)
        assert "* [Active] Learn Sanskrit" in frame
        assert "[Active] PAIOS" in frame
        assert "[########............] 40%" in frame

    def test_completed_today_appears_in_today_section(self, dash_app):
        recommendation = tick_and_get_rest_recommendation(dash_app)
        dash_app.accept_recommendation(recommendation.recommendation_id)
        event = dash_app.list_events()[0]
        dash_app.start_event(event.event_id)
        dash_app.complete_event(event.event_id)
        frame = frame_of(dash_app)
        assert "Completed: 1" in frame
        assert "No running event." in frame

    def test_health_section_shows_energy_resource(self, dash_app):
        assert "Energy: 10 points" in frame_of(dash_app)

    def test_learning_section_reflects_study_activity(self, dash_app):
        knowledge = dash_app.add_knowledge(
            USER, "Programming", "Python", "Dataclasses"
        )
        dash_app.revise_knowledge(knowledge.knowledge_id, confidence=50.0)
        frame = frame_of(dash_app)
        assert "Study:             last 2026-07-21, 1 revised today" in frame

    def test_system_section_states(self, dash_app):
        frame = frame_of(dash_app)
        assert "Scheduler:       Idle" in frame
        assert "Decision Engine: stateless (ready)" in frame
        assert "Kernel:          Running (operational: yes)" in frame


class TestDelegation:
    def test_renderer_uses_only_readonly_facade_queries(self, recording_app):
        frame = DashboardRenderer(recording_app).render()
        assert "PAIOS DASHBOARD" in frame
        assert set(recording_app.calls) <= ALLOWED_QUERIES
        # And it genuinely consulted the facade for each data family.
        assert {
            "current_time",
            "status",
            "scheduler_state",
            "list_events",
            "list_goals",
            "list_projects",
            "active_recommendations",
        } <= set(recording_app.calls)
