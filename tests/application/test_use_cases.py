"""High-level use cases through the facade — the complete canonical loop
running as one application."""

import pytest

from paios.domain.enums import (
    DisturberResolutionStatus,
    DisturberSeverity,
    DisturberState,
    DisturberType,
    EventOutcomeType,
    EventStatus,
    RecommendationStatus,
)
from paios.domain.value_objects.event_outcome import EventOutcome
from paios.domain.value_objects.identifiers import EventDisturberId

from tests.application.conftest import USER, at


def tick_and_get_rest_recommendation(application):
    result = application.tick()
    return next(
        r.recommendation
        for r in result.recommendations
        if r.recommendation.reason.startswith("Energy is low")
    )


class TestRecommendationDecisions:
    def test_accept_materializes_and_persists_an_event(self, started_app):
        recommendation = tick_and_get_rest_recommendation(started_app)
        started_app.accept_recommendation(recommendation.recommendation_id)
        assert recommendation.status is RecommendationStatus.CONSUMED
        events = started_app.components.kernel.runtime_state.events
        assert len(events) == 1
        assert events[0].description == recommendation.reason
        stored = started_app.components.repositories.events().list()
        assert len(stored) == 1

    def test_reject_is_recorded_and_persisted(self, started_app):
        recommendation = tick_and_get_rest_recommendation(started_app)
        started_app.reject_recommendation(
            recommendation.recommendation_id, reason="Feeling fine"
        )
        assert recommendation.status is RecommendationStatus.REJECTED
        stored = started_app.components.repositories.recommendations().get(
            recommendation.recommendation_id
        )
        assert stored.status is RecommendationStatus.REJECTED
        assert started_app.active_recommendations() == ()


class TestEventExecution:
    def accept_and_start(self, application):
        recommendation = tick_and_get_rest_recommendation(application)
        application.accept_recommendation(recommendation.recommendation_id)
        event = application.components.kernel.runtime_state.events[0]
        application.start_event(event.event_id)
        return event

    def test_full_golden_path(self, started_app):
        event = self.accept_and_start(started_app)
        assert event.status is EventStatus.STARTED
        started_app.complete_event(
            event.event_id,
            at=at(45),
            outcome=EventOutcome(EventOutcomeType.COMPLETED, at(45)),
            actual_outcome="Rested well",
        )
        assert event.status is EventStatus.COMPLETED
        stored = started_app.components.repositories.events().get(
            event.event_id
        )
        assert stored.status is EventStatus.COMPLETED
        assert stored.outcome.outcome_type is EventOutcomeType.COMPLETED
        assert stored.actual_outcome == "Rested well"

    def test_pause_and_resume(self, started_app):
        event = self.accept_and_start(started_app)
        started_app.pause_event(event.event_id, at=at(10))
        assert event.status is EventStatus.PAUSED
        started_app.resume_event(event.event_id, at=at(20))
        assert event.status is EventStatus.RESUMED
        assert event.is_running

    def test_cancel_ready_event(self, started_app):
        recommendation = tick_and_get_rest_recommendation(started_app)
        started_app.accept_recommendation(recommendation.recommendation_id)
        event = started_app.components.kernel.runtime_state.events[0]
        assert event.status is EventStatus.READY
        started_app.cancel_event(event.event_id, reason="Changed plans")
        assert event.status is EventStatus.CANCELLED

    def test_archive_after_completion(self, started_app):
        event = self.accept_and_start(started_app)
        started_app.complete_event(event.event_id, at=at(45))
        started_app.archive_event(event.event_id, at=at(500))
        assert event.status is EventStatus.ARCHIVED

    def test_spontaneous_action_through_facade(self, started_app):
        event = started_app.report_spontaneous_action(
            USER, "health", "Went for an unplanned walk"
        )
        assert event.status is EventStatus.STARTED
        stored = started_app.components.repositories.events().get(
            event.event_id
        )
        assert stored.status is EventStatus.STARTED


class TestDisturbers:
    def test_disturber_with_running_event_runs_the_mandatory_chain(
        self, started_app
    ):
        running = started_app.report_spontaneous_action(
            USER, "study", "Deep work session"
        )
        disturber = started_app.report_disturber(
            USER,
            DisturberType.WORK,
            "Team Lead requested overtime",
            DisturberSeverity.HIGH,
            disturber_id=EventDisturberId("dist_001"),
        )
        assert running.status is EventStatus.INTERRUPTED
        assert disturber.state is DisturberState.RESOLVED
        assert disturber.resolution_status is DisturberResolutionStatus.RESOLVED
        stored = started_app.components.repositories.event_disturbers().get(
            EventDisturberId("dist_001")
        )
        assert stored.state is DisturberState.RESOLVED
        assert started_app.active_event_disturbers() == ()

    def test_disturber_without_active_window_stays_analyzed_evidence(
        self, started_app
    ):
        disturber = started_app.report_disturber(
            USER,
            DisturberType.HEALTH,
            "Sudden headache",
            DisturberSeverity.MEDIUM,
            disturber_id=EventDisturberId("dist_002"),
        )
        assert disturber.state is DisturberState.ANALYZED
        assert len(started_app.active_event_disturbers()) == 1
        stored = started_app.components.repositories.event_disturbers().get(
            EventDisturberId("dist_002")
        )
        assert stored.state is DisturberState.ANALYZED

    def test_interrupted_event_can_resume_after_disturbance(self, started_app):
        running = started_app.report_spontaneous_action(
            USER, "study", "Deep work session"
        )
        started_app.report_disturber(
            USER,
            DisturberType.WORK,
            "Interruption",
            DisturberSeverity.LOW,
            disturber_id=EventDisturberId("dist_003"),
        )
        started_app.resume_event(running.event_id, at=at(30))
        assert running.is_running


class TestTimeHandling:
    def test_explicit_at_overrides_the_clock(self, started_app):
        event = started_app.report_spontaneous_action(
            USER, "health", "Walk", at=at(15)
        )
        assert event.start_time == at(15)

    def test_default_moments_come_from_the_injected_clock(
        self, started_app
    ):
        from tests.application.conftest import T0

        event = started_app.report_spontaneous_action(USER, "health", "Walk")
        assert event.start_time == T0
