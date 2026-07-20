"""Recommendation flow: accept, consume/materialize (G1), expire, defer,
user rejection (G8) — with persistence write-back (G2) verified."""

import pytest

from paios.domain.enums import EventStatus, RecommendationStatus
from paios.domain.errors import RecommendationExpiredError
from paios.domain.value_objects.identifiers import RecommendationId

from tests.scheduler.conftest import (
    at,
    build_pending_recommendation,
    publish_time,
    seed_context,
)

REC = RecommendationId("rec_001")


def seed_rec_and_context(factory):
    seed_context(factory)
    factory.recommendations().save(build_pending_recommendation())


class TestAcceptAndConsume:
    def test_accept_materializes_scheduled_event(self, system):
        wired = system(seed=seed_rec_and_context)
        wired.scheduler.accept_recommendation(REC, at(5))
        state = wired.kernel.runtime_state
        assert len(state.events) == 1
        event = state.events[0]
        # No suggested timing -> the slot is due immediately, so the Event
        # legally advances Scheduled -> Ready within the accept cascade.
        assert event.status is EventStatus.READY
        assert [record.to_state for record in event.transitions] == [
            EventStatus.SCHEDULED,
            EventStatus.READY,
        ]
        assert event.category == "recommendation"
        assert event.description == "Study ISTQB Chapter 5"
        assert event.expected_outcome == "Chapter 5 mastery"
        window = state.context_windows[0]
        assert window.event_id == event.event_id
        assert str(window.context_id) == "ctx_001"
        recommendation = state.recommendations[0]
        assert recommendation.status is RecommendationStatus.CONSUMED

    def test_materialized_aggregates_are_persisted(self, system):
        wired = system(seed=seed_rec_and_context)
        wired.scheduler.accept_recommendation(REC, at(5))
        assert len(wired.factory.events().list()) == 1
        assert len(wired.factory.context_windows().list()) == 1
        stored_rec = wired.factory.recommendations().get(REC)
        assert stored_rec.status is RecommendationStatus.CONSUMED

    def test_plan_contains_the_new_event(self, system):
        wired = system(seed=seed_rec_and_context)
        wired.scheduler.accept_recommendation(REC, at(5))
        plan = wired.scheduler.plan
        assert len(plan.entries) == 1
        assert plan.entries[0].priority == 5.0
        assert plan.entries[0].recommendation_id == REC

    def test_consumption_deferred_without_any_context(self, system):
        wired = system(
            seed=lambda factory: factory.recommendations().save(
                build_pending_recommendation()
            )
        )
        wired.scheduler.accept_recommendation(REC, at(5))
        state = wired.kernel.runtime_state
        assert state.recommendations[0].status is RecommendationStatus.ACCEPTED
        assert len(state.events) == 0
        publish_time(wired.kernel, at(10))
        assert state.recommendations[0].status is RecommendationStatus.ACCEPTED


class TestExpiryAndRejection:
    def test_expired_recommendation_cannot_be_accepted(self, system):
        wired = system(seed=seed_rec_and_context)
        with pytest.raises(RecommendationExpiredError):
            wired.scheduler.accept_recommendation(REC, at(120))

    def test_time_progression_expires_pending(self, system):
        wired = system(seed=seed_rec_and_context)
        publish_time(wired.kernel, at(150))
        recommendation = wired.kernel.runtime_state.recommendations[0]
        assert recommendation.status is RecommendationStatus.EXPIRED
        assert (
            wired.factory.recommendations().get(REC).status
            is RecommendationStatus.EXPIRED
        )

    def test_user_rejection_is_applied_and_persisted(self, system):
        wired = system(seed=seed_rec_and_context)
        wired.scheduler.user_rejected_recommendation(
            REC, at(5), reason="Not now"
        )
        assert (
            wired.factory.recommendations().get(REC).status
            is RecommendationStatus.REJECTED
        )

    def test_scheduler_never_rejects_on_its_own(self, system):
        # Infeasible consumption defers (stays Accepted); it never becomes
        # Rejected without a user decision (G8).
        wired = system(
            seed=lambda factory: factory.recommendations().save(
                build_pending_recommendation()
            )
        )
        wired.scheduler.accept_recommendation(REC, at(5))
        for minutes in (10, 20, 30):
            publish_time(wired.kernel, at(minutes))
        assert (
            wired.kernel.runtime_state.recommendations[0].status
            is RecommendationStatus.ACCEPTED
        )
