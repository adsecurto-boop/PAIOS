"""Recommendation lifecycle (STATE_MACHINES.md section 6, Resolution 4)."""

import pytest

from paios.domain.enums import RecommendationStatus
from paios.domain.errors import (
    DomainValidationError,
    InvalidTransitionError,
    RecommendationExpiredError,
)

from tests.domain.conftest import T0, at


class TestRecommendationLifecycle:
    def test_starts_generated(self, make_recommendation):
        assert make_recommendation().status is RecommendationStatus.GENERATED

    def test_expiry_must_follow_creation(self, make_recommendation):
        with pytest.raises(DomainValidationError):
            make_recommendation(created_at=T0, expires_at=T0)

    def test_accept_path_to_consumed(self, make_recommendation):
        recommendation = make_recommendation()
        recommendation.present(at(1))
        recommendation.accept(at(2))
        recommendation.consume(at(3))
        assert recommendation.status is RecommendationStatus.CONSUMED

    def test_reject_is_terminal_historical_evidence(self, make_recommendation):
        recommendation = make_recommendation()
        recommendation.present(at(1))
        recommendation.reject(at(2), reason="User declined")
        assert recommendation.status is RecommendationStatus.REJECTED
        with pytest.raises(InvalidTransitionError):
            recommendation.accept(at(3))
        assert recommendation.transitions[-1].reason == "User declined"

    def test_expired_cannot_be_accepted_by_state(self, make_recommendation):
        recommendation = make_recommendation()
        recommendation.present(at(1))
        recommendation.expire(at(2), reason="Context changed")
        with pytest.raises(InvalidTransitionError):
            recommendation.accept(at(3))

    def test_expired_by_time_cannot_be_accepted(self, make_recommendation):
        recommendation = make_recommendation(expires_at=at(30))
        recommendation.present(at(1))
        with pytest.raises(RecommendationExpiredError):
            recommendation.accept(at(30))

    def test_is_expired_relative_to_current_time(self, make_recommendation):
        recommendation = make_recommendation(expires_at=at(30))
        assert not recommendation.is_expired(at(29))
        assert recommendation.is_expired(at(30))


class TestInvalidRecommendationTransitions:
    """Invalid: Generated -> Accepted; Pending -> Consumed (STATE_MACHINES.md)."""

    def test_cannot_accept_before_presentation(self, make_recommendation):
        with pytest.raises(InvalidTransitionError):
            make_recommendation().accept(at(1))

    def test_cannot_consume_before_acceptance(self, make_recommendation):
        recommendation = make_recommendation()
        recommendation.present(at(1))
        with pytest.raises(InvalidTransitionError):
            recommendation.consume(at(2))

    def test_transition_history_cannot_be_replaced(self, make_recommendation):
        from paios.domain.enums import RecommendationStatus as RS
        from paios.domain.errors import ImmutabilityViolationError
        from paios.domain.state_machines.definitions import (
            RECOMMENDATION_STATE_MACHINE,
        )
        from paios.domain.state_machines.machine import TransitionHistory

        recommendation = make_recommendation()
        recommendation.present(at(1))
        recommendation.reject(at(2))
        with pytest.raises(ImmutabilityViolationError):
            recommendation._history = TransitionHistory(
                RECOMMENDATION_STATE_MACHINE, RS.GENERATED
            )
