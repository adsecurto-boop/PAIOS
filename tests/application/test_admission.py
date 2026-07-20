"""The approved M6 correction: Recommendation / Event Disturber admission
and the active-only consumption surfaces."""

import pytest

from paios.domain.entities.event_disturber import EventDisturber
from paios.domain.entities.recommendation import Recommendation
from paios.domain.enums import (
    DisturberSeverity,
    DisturberState,
    DisturberType,
    RecommendationStatus,
)
from paios.domain.value_objects.identifiers import (
    ContextWindowId,
    EventDisturberId,
    RecommendationId,
)
from paios.runtime.exceptions import RuntimeInvariantError

from tests.application.conftest import T0, USER, at


def make_recommendation(rid: str = "rec_new") -> Recommendation:
    return Recommendation(
        recommendation_id=RecommendationId(rid),
        user_id=USER,
        reason="Handmade suggestion",
        created_at=T0,
        expires_at=at(60),
    )


def make_disturber(did: str = "dist_new") -> EventDisturber:
    return EventDisturber(
        event_disturber_id=EventDisturberId(did),
        user_id=USER,
        type=DisturberType.HEALTH,
        description="Sudden headache",
        severity=DisturberSeverity.MEDIUM,
        occurred_at=T0,
    )


class TestRecommendationAdmission:
    def test_admitted_recommendation_enters_state_and_storage(self, started_app):
        kernel = started_app.components.kernel
        recommendation = make_recommendation()
        kernel.admit_recommendation(recommendation)
        assert recommendation in kernel.runtime_state.recommendations
        assert recommendation in kernel.runtime_state.active_recommendations
        stored = started_app.components.repositories.recommendations().get(
            RecommendationId("rec_new")
        )
        assert stored.status is RecommendationStatus.GENERATED

    def test_admission_refreshes_snapshot(self, started_app):
        kernel = started_app.components.kernel
        kernel.admit_recommendation(make_recommendation())
        assert any(
            str(r.recommendation_id) == "rec_new"
            for r in kernel.latest_snapshot.recommendations
        )

    def test_duplicate_admission_rejected(self, started_app):
        kernel = started_app.components.kernel
        kernel.admit_recommendation(make_recommendation())
        with pytest.raises(RuntimeInvariantError):
            kernel.admit_recommendation(make_recommendation())

    def test_active_filter_excludes_terminal_recommendations(self, started_app):
        kernel = started_app.components.kernel
        rejected = make_recommendation("rec_rejected")
        rejected.present(at(1))
        rejected.reject(at(2))
        expired = make_recommendation("rec_expired")
        expired.present(at(1))
        expired.expire(at(2))
        live = make_recommendation("rec_live")
        for recommendation in (rejected, expired, live):
            kernel.admit_recommendation(recommendation)
        active_ids = {
            str(r.recommendation_id)
            for r in kernel.runtime_state.active_recommendations
        }
        assert active_ids == {"rec_live"}

    def test_admitted_recommendation_is_acceptable_end_to_end(self, started_app):
        kernel = started_app.components.kernel
        recommendation = make_recommendation()
        recommendation.present(T0)
        kernel.admit_recommendation(recommendation)
        started_app.accept_recommendation(RecommendationId("rec_new"))
        assert recommendation.status is RecommendationStatus.CONSUMED
        assert len(kernel.runtime_state.events) == 1  # materialized


class TestDisturberAdmission:
    def test_admitted_disturber_enters_state_and_storage(self, started_app):
        kernel = started_app.components.kernel
        kernel.admit_event_disturber(make_disturber())
        assert len(kernel.runtime_state.event_disturbers) == 1
        stored = started_app.components.repositories.event_disturbers().get(
            EventDisturberId("dist_new")
        )
        assert stored.state is DisturberState.DETECTED

    def test_duplicate_disturber_rejected(self, started_app):
        kernel = started_app.components.kernel
        kernel.admit_event_disturber(make_disturber())
        with pytest.raises(RuntimeInvariantError):
            kernel.admit_event_disturber(make_disturber())

    def test_active_filter_excludes_completed_lifecycles(self, started_app):
        kernel = started_app.components.kernel
        detected = make_disturber("dist_detected")
        resolved = make_disturber("dist_resolved")
        resolved.record(at(1))
        resolved.analyze(at(2))
        resolved.apply(at(3), ContextWindowId("win_x"))
        resolved.resolve(at(4))
        kernel.admit_event_disturber(detected)
        kernel.admit_event_disturber(resolved)
        active_ids = {
            str(d.event_disturber_id)
            for d in kernel.runtime_state.active_event_disturbers
        }
        assert active_ids == {"dist_detected"}

    def test_facade_exposes_active_surfaces(self, started_app):
        kernel = started_app.components.kernel
        kernel.admit_recommendation(make_recommendation())
        kernel.admit_event_disturber(make_disturber())
        assert len(started_app.active_recommendations()) == 1
        assert len(started_app.active_event_disturbers()) == 1
