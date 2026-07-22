"""M20 additive facade surface: propose/edit/duplicate/plan.

Proves the composition rides EXISTING calls end to end: the intent is
admitted as a Recommendation, the Scheduler (not the facade) turns it
into a Scheduled Event, and the plan query is pure read-only.
"""

from datetime import timedelta

import pytest

from paios.domain.enums import EventStatus, RecommendationStatus
from paios.repositories.errors import EntityNotFound
from paios.domain.value_objects.identifiers import EventId

from tests.application.conftest import T0, USER


def event_by_id(application, event_id):
    return next(
        event
        for event in application.list_events()
        if event.event_id == event_id
    )


class TestProposeUserEvent:
    def test_intent_materializes_through_the_scheduler(self, started_app):
        recommendation, event_id = started_app.propose_user_event(
            USER,
            "Buy medicine",
            suggested_time=T0 + timedelta(hours=8),
            priority=2.0,
        )
        assert recommendation.status is RecommendationStatus.CONSUMED
        assert event_id is not None
        event = event_by_id(started_app, event_id)
        assert event.status is EventStatus.SCHEDULED
        assert event.description == "Buy medicine"
        # The Scheduler's materialization marker: user intents become
        # Events exactly the way engine recommendations do (G1).
        assert event.category == "recommendation"

    def test_plan_carries_the_intent_at_its_suggested_time(self, started_app):
        _, event_id = started_app.propose_user_event(
            USER, "Gym", suggested_time=T0 + timedelta(hours=9)
        )
        plan = started_app.plan()
        entry = next(
            entry for entry in plan.entries if entry.event_id == event_id
        )
        assert entry.planned_start >= T0 + timedelta(hours=9)

    def test_without_auto_accept_recommendation_stays_pending(
        self, started_app
    ):
        recommendation, event_id = started_app.propose_user_event(
            USER, "Read chapter 4", auto_accept=False
        )
        assert recommendation.status is RecommendationStatus.PENDING
        assert event_id is None
        # The normal user-accept path finishes the job.
        started_app.accept_recommendation(recommendation.recommendation_id)
        assert recommendation.status is RecommendationStatus.CONSUMED


class TestEditAndDuplicate:
    def test_edit_cancels_original_and_proposes_replacement(
        self, started_app
    ):
        _, original_id = started_app.propose_user_event(USER, "Study ISTQB")
        recommendation, new_id = started_app.edit_event(
            original_id, USER, "Study ISTQB chapter 5"
        )
        original = event_by_id(started_app, original_id)
        assert original.status is EventStatus.CANCELLED
        assert "superseded" in original.transitions[-1].reason
        assert event_by_id(started_app, new_id).description == (
            "Study ISTQB chapter 5"
        )

    def test_duplicate_copies_description_and_project(self, started_app):
        _, source_id = started_app.propose_user_event(USER, "Temple")
        _, copy_id = started_app.duplicate_event(
            source_id, suggested_time=T0 + timedelta(days=1)
        )
        assert copy_id is not None and copy_id != source_id
        assert event_by_id(started_app, copy_id).description == "Temple"

    def test_duplicate_unknown_event_raises_not_found(self, started_app):
        with pytest.raises(EntityNotFound):
            started_app.duplicate_event(EventId("ev_missing"))


class TestPlanQuery:
    def test_plan_is_read_only_scheduler_output(self, started_app):
        before = started_app.plan()
        assert started_app.plan() is before  # same object, pure delegation
