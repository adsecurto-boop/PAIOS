"""The runtime loop pass: tick, run, and pure evaluate."""

from paios.domain.enums import RecommendationStatus


class TestEvaluate:
    def test_evaluate_is_pure(self, started_app):
        result = started_app.evaluate()
        assert not result.no_action  # rest scenario fires
        assert started_app.active_recommendations() == ()  # nothing admitted
        assert (
            started_app.components.repositories.recommendations().list() == []
        )


class TestTick:
    def test_tick_presents_and_admits_recommendations(self, started_app):
        result = started_app.tick()
        assert not result.no_action
        active = started_app.active_recommendations()
        assert len(active) == len(result.recommendations)
        assert all(
            recommendation.status is RecommendationStatus.PENDING
            for recommendation in active
        )

    def test_tick_persists_recommendations(self, started_app):
        started_app.tick()
        stored = started_app.components.repositories.recommendations().list()
        assert len(stored) == len(started_app.active_recommendations())
        assert all(
            recommendation.status is RecommendationStatus.PENDING
            for recommendation in stored
        )

    def test_tick_carries_full_explanations(self, started_app):
        result = started_app.tick()
        rest = next(
            r
            for r in result.recommendations
            if r.recommendation.reason.startswith("Energy is low")
        )
        assert rest.explanation.principles_influenced == ("Protect Health",)
        assert rest.explanation.facts_used

    def test_second_tick_does_not_duplicate_pending_suggestions(
        self, started_app
    ):
        started_app.tick()
        count = len(started_app.active_recommendations())
        second = started_app.tick()
        assert len(started_app.active_recommendations()) == count
        assert second.recommendations == ()  # all redundant now
        assert any(
            "Already recommended" in rejected.reason
            for rejected in second.rejected
        )

    def test_tick_on_empty_store_is_valid_no_action(self, app_builder):
        application = app_builder()
        application.start()
        result = application.tick()
        assert result.no_action
        assert application.active_recommendations() == ()
        application.stop()


class TestRun:
    def test_bounded_run_returns_one_result_per_iteration(self, started_app):
        results = started_app.run(3)
        assert len(results) == 3
        # First pass recommends; later passes deduplicate deterministically.
        assert not results[0].no_action
        assert results[1].recommendations == ()
        assert results[2].recommendations == ()

    def test_run_zero_iterations_is_a_noop(self, started_app):
        assert started_app.run(0) == ()
