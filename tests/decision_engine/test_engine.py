"""The full engine: determinism, purity, explainability, edge cases."""

from datetime import timedelta

import pytest

from paios.domain.enums import EventStatus, RecommendationStatus
from paios.decision_engine.engine import (
    MAX_RECOMMENDATIONS,
    DecisionEngine,
)
from paios.decision_engine.exceptions import InvalidSnapshotError
from paios.decision_engine.recommendation_builder import (
    RECOMMENDATION_VALIDITY_MINUTES,
)
from paios.decision_engine.rules import Candidate, Rule

from tests.decision_engine.conftest import (
    T0,
    USER,
    at,
    energy_resource,
    event_in_state,
    full_snapshot,
    make_snapshot,
)


class TestEmptyAndInvalidSnapshots:
    def test_empty_snapshot_yields_valid_no_action(self):
        result = DecisionEngine().evaluate(make_snapshot())
        assert result.no_action
        assert result.recommendations == ()
        assert "valid" in result.no_action_reason

    def test_two_running_events_rejected(self):
        snapshot = make_snapshot(
            events=(
                event_in_state("evt_1", EventStatus.STARTED),
                event_in_state("evt_2", EventStatus.STARTED),
            )
        )
        with pytest.raises(InvalidSnapshotError):
            DecisionEngine().evaluate(snapshot)

    def test_non_snapshot_rejected(self):
        with pytest.raises(InvalidSnapshotError):
            DecisionEngine().evaluate({"not": "a snapshot"})


class TestFullSnapshot:
    def test_produces_capped_ranked_recommendations(self):
        result = DecisionEngine().evaluate(full_snapshot())
        assert not result.no_action
        assert 1 <= len(result.recommendations) <= MAX_RECOMMENDATIONS
        totals = [r.score.total for r in result.recommendations]
        assert totals == sorted(totals, reverse=True)

    def test_recommendations_are_generated_domain_entities(self):
        result = DecisionEngine().evaluate(full_snapshot())
        for reasoned in result.recommendations:
            recommendation = reasoned.recommendation
            assert recommendation.status is RecommendationStatus.GENERATED
            assert recommendation.user_id == USER
            assert recommendation.created_at == T0
            assert recommendation.expires_at == T0 + timedelta(
                minutes=RECOMMENDATION_VALIDITY_MINUTES
            )
            assert recommendation.priority == reasoned.score.total
            assert recommendation.confidence_score == reasoned.confidence.value

    def test_every_recommendation_is_fully_explained(self):
        result = DecisionEngine().evaluate(full_snapshot())
        for reasoned in result.recommendations:
            explanation = reasoned.explanation
            assert explanation.why
            assert explanation.facts_used
            assert explanation.expected_impact
            assert explanation.confidence_level in ("High", "Medium", "Low")
            assert explanation.score_components
        rest = next(
            r
            for r in result.recommendations
            if r.recommendation.reason.startswith("Energy is low")
        )
        assert rest.explanation.principles_influenced == ("Protect Health",)

    def test_priority_evaluation_matches_recommendations(self):
        result = DecisionEngine().evaluate(full_snapshot())
        assert result.priority_evaluation == tuple(
            (r.recommendation.reason, r.score.total)
            for r in result.recommendations
        )


class TestDeterminism:
    def test_identical_snapshots_produce_identical_results(self):
        first = DecisionEngine().evaluate(full_snapshot())
        second = DecisionEngine().evaluate(full_snapshot())
        assert [str(r.recommendation.recommendation_id) for r in first.recommendations] == [
            str(r.recommendation.recommendation_id) for r in second.recommendations
        ]
        assert [r.recommendation.reason for r in first.recommendations] == [
            r.recommendation.reason for r in second.recommendations
        ]
        assert [r.score.total for r in first.recommendations] == [
            r.score.total for r in second.recommendations
        ]
        assert first.priority_evaluation == second.priority_evaluation

    def test_repeated_evaluation_on_one_engine_is_stable(self):
        engine = DecisionEngine()
        snapshot = full_snapshot()
        results = [engine.evaluate(snapshot) for _ in range(3)]
        ids = [
            tuple(str(r.recommendation.recommendation_id) for r in result.recommendations)
            for result in results
        ]
        assert ids[0] == ids[1] == ids[2]

    def test_different_snapshot_time_changes_ids_deterministically(self):
        early = DecisionEngine().evaluate(
            make_snapshot(resources=(energy_resource(10.0),))
        )
        late = DecisionEngine().evaluate(
            make_snapshot(
                current_time=at(30), resources=(energy_resource(10.0),)
            )
        )
        assert (
            early.recommendations[0].recommendation.recommendation_id
            != late.recommendations[0].recommendation.recommendation_id
        )


class TestPurity:
    def test_evaluate_mutates_nothing_in_the_snapshot(self):
        snapshot = full_snapshot()
        transition_counts = [len(event.transitions) for event in snapshot.events]
        statuses = [event.status for event in snapshot.events]
        DecisionEngine().evaluate(snapshot)
        assert [len(e.transitions) for e in snapshot.events] == transition_counts
        assert [e.status for e in snapshot.events] == statuses
        assert all(
            r.status is not RecommendationStatus.CONSUMED
            for r in snapshot.recommendations
        )

    def test_engine_holds_no_state_between_calls(self):
        engine = DecisionEngine()
        engine.evaluate(full_snapshot())
        empty_result = engine.evaluate(make_snapshot())
        assert empty_result.no_action


class TestConflictsAndCustomRules:
    def test_conflicting_candidates_rank_deterministically(self):
        class FixedRule(Rule):
            def __init__(self, rule_id, key):
                self.rule_id = rule_id
                self._key = key

            def evaluate(self, snapshot):
                return (
                    Candidate(
                        rule_id=self.rule_id,
                        key=self._key,
                        action="Tied action",
                        reason=f"Tied action {self._key}",
                        expected_benefit="Benefit",
                        user_id=USER,
                        base_priority=5.0,
                        category="tie",
                    ),
                )

        engine = DecisionEngine(
            rules=(FixedRule("rule-b", "b"), FixedRule("rule-a", "a"))
        )
        result = engine.evaluate(make_snapshot())
        assert [r.recommendation.reason for r in result.recommendations] == [
            "Tied action a",
            "Tied action b",
        ]

    def test_rejections_are_reported_not_silent(self):
        class ViolatingRule(Rule):
            rule_id = "violator"

            def evaluate(self, snapshot):
                return (
                    Candidate(
                        rule_id=self.rule_id,
                        key="v1",
                        action="Harmful action",
                        reason="Harmful action",
                        expected_benefit="None",
                        user_id=USER,
                        base_priority=9.0,
                        category="harm",
                        violates_principles=("Protect Health",),
                    ),
                )

        result = DecisionEngine(rules=(ViolatingRule(),)).evaluate(
            make_snapshot()
        )
        assert result.no_action
        assert len(result.rejected) == 1
        assert "Violates Principle" in result.rejected[0].reason
