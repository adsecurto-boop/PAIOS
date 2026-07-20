"""Composition-level determinism and facade guard rails."""

from datetime import timedelta

import pytest

from paios.application.application import Application
from paios.application.config import ApplicationConfig
from paios.application.exceptions import ApplicationNotStartedError
from paios.domain.errors import RecommendationExpiredError
from paios.domain.value_objects.identifiers import EventId, RecommendationId, UserId
from paios.repositories.factory import RepositoryFactory
from paios.runtime.clock import ManualClock
from paios.scheduler.exceptions import UnknownWorkError

from tests.application.conftest import T0, USER, seed_rest_scenario


def build_isolated_app(tmp_path, name: str) -> Application:
    data_dir = tmp_path / name
    factory = RepositoryFactory(data_dir)
    factory.initialize()
    seed_rest_scenario(factory)
    return Application(
        ApplicationConfig(data_dir=data_dir, clock=ManualClock(T0))
    )


class TestDeterministicComposition:
    def test_identical_seeds_produce_identical_recommendations(self, tmp_path):
        first = build_isolated_app(tmp_path, "a")
        second = build_isolated_app(tmp_path, "b")
        first.start()
        second.start()
        first_ids = [
            str(r.recommendation.recommendation_id)
            for r in first.tick().recommendations
        ]
        second_ids = [
            str(r.recommendation.recommendation_id)
            for r in second.tick().recommendations
        ]
        assert first_ids == second_ids
        first.stop()
        second.stop()

    def test_recommendation_ids_survive_restart(self, app_builder):
        application = app_builder(seed=seed_rest_scenario)
        application.start()
        application.tick()
        original_ids = {
            str(r.recommendation_id)
            for r in application.active_recommendations()
        }
        application.stop()
        application = app_builder()
        application.start()
        restored_ids = {
            str(r.recommendation_id)
            for r in application.active_recommendations()
        }
        assert restored_ids == original_ids
        application.stop()

    def test_all_timestamps_derive_from_the_injected_clock(self, started_app):
        result = started_app.tick()
        for reasoned in result.recommendations:
            assert reasoned.recommendation.created_at == T0
            assert reasoned.recommendation.expires_at == T0 + timedelta(
                minutes=60
            )

    def test_facade_evaluate_is_repeatable(self, started_app):
        first = started_app.evaluate()
        second = started_app.evaluate()
        assert [
            str(r.recommendation.recommendation_id)
            for r in first.recommendations
        ] == [
            str(r.recommendation.recommendation_id)
            for r in second.recommendations
        ]


class TestFacadeGuards:
    def test_user_actions_require_a_started_application(self, app_builder):
        application = app_builder()
        with pytest.raises(ApplicationNotStartedError):
            application.accept_recommendation(RecommendationId("rec_x"))
        with pytest.raises(ApplicationNotStartedError):
            application.start_event(EventId("evt_x"))
        with pytest.raises(ApplicationNotStartedError):
            application.report_spontaneous_action(USER, "health", "Walk")

    def test_unknown_recommendation_surfaces_scheduler_error(self, started_app):
        with pytest.raises(UnknownWorkError):
            started_app.accept_recommendation(RecommendationId("rec_missing"))

    def test_unknown_event_surfaces_scheduler_error(self, started_app):
        with pytest.raises(UnknownWorkError):
            started_app.start_event(EventId("evt_missing"))

    def test_expired_recommendation_cannot_be_accepted_end_to_end(
        self, started_app
    ):
        result = started_app.tick()
        recommendation = result.recommendations[0].recommendation
        started_app.components.clock.advance(timedelta(minutes=61))
        with pytest.raises(RecommendationExpiredError):
            started_app.accept_recommendation(recommendation.recommendation_id)

    def test_domain_guards_reach_through_the_facade(self, started_app):
        event = started_app.report_spontaneous_action(USER, "health", "Walk")
        started_app.complete_event(event.event_id)
        from paios.domain.errors import InvalidTransitionError

        with pytest.raises(InvalidTransitionError):
            started_app.start_event(event.event_id)
