"""Filters (§5, ordered, recorded), scoring (§6, decomposed), and
confidence (§7, factor-based)."""

from paios.domain.enums import EventStatus, ImpactType
from paios.decision_engine.confidence import (
    ConfidenceLevel,
    compute_confidence,
)
from paios.decision_engine.evaluator import CandidateFilter
from paios.decision_engine.rules import Candidate
from paios.decision_engine.scoring import rank_candidates, score_candidate

from tests.decision_engine.conftest import (
    USER,
    energy_resource,
    event_in_state,
    make_snapshot,
    pending_recommendation,
)


def candidate(**overrides) -> Candidate:
    fields = dict(
        rule_id="test-rule",
        key="k1",
        action="Do the thing",
        reason="Do the thing now",
        expected_benefit="Benefit",
        user_id=USER,
        base_priority=5.0,
        category="study",
    )
    fields.update(overrides)
    return Candidate(**fields)


class TestFilters:
    def test_principle_violation_rejected_first(self):
        accepted, rejected = CandidateFilter().apply(
            make_snapshot(),
            (candidate(violates_principles=("Protect Health",)),),
        )
        assert accepted == ()
        assert "Violates Principle" in rejected[0].reason

    def test_insufficient_energy_rejected(self):
        snapshot = make_snapshot(resources=(energy_resource(10.0),))
        accepted, rejected = CandidateFilter().apply(
            snapshot, (candidate(required_energy=50.0),)
        )
        assert accepted == ()
        assert "Insufficient Energy" in rejected[0].reason

    def test_untracked_energy_passes_feasibility(self):
        accepted, rejected = CandidateFilter().apply(
            make_snapshot(), (candidate(required_energy=50.0),)
        )
        assert len(accepted) == 1 and rejected == ()

    def test_redundant_pending_recommendation_rejected(self):
        snapshot = make_snapshot(
            recommendations=(pending_recommendation("Do the thing now"),)
        )
        accepted, rejected = CandidateFilter().apply(
            snapshot, (candidate(),)
        )
        assert accepted == ()
        assert "Already recommended" in rejected[0].reason

    def test_clean_candidate_passes(self):
        accepted, rejected = CandidateFilter().apply(
            make_snapshot(), (candidate(),)
        )
        assert len(accepted) == 1 and rejected == ()


class TestScoring:
    def test_components_are_named_and_summed(self):
        score = score_candidate(
            make_snapshot(),
            candidate(momentum=True, goal_aligned=True),
        )
        assert score.components["base_priority"] == 5.0
        assert score.components["momentum_preservation"] == 1.5
        assert score.components["goal_contribution"] == 2.0
        assert score.total == 8.5

    def test_historical_impact_moves_the_score(self):
        opportunity_history = make_snapshot(
            events=(
                event_in_state(
                    "evt_1", EventStatus.COMPLETED, impact=ImpactType.OPPORTUNITY
                ),
            )
        )
        distraction_history = make_snapshot(
            events=(
                event_in_state(
                    "evt_1", EventStatus.COMPLETED, impact=ImpactType.DISTRACTION
                ),
            )
        )
        plain = candidate()
        up = score_candidate(opportunity_history, plain)
        down = score_candidate(distraction_history, plain)
        assert up.components["historical_success"] == 1.0
        assert down.components["historical_success"] == -1.0

    def test_ranking_is_deterministic_with_stable_tiebreak(self):
        pair = (
            candidate(key="b", rule_id="rule-b"),
            candidate(key="a", rule_id="rule-a"),
        )
        ranked = rank_candidates(make_snapshot(), pair)
        assert [c.rule_id for c, _ in ranked] == ["rule-a", "rule-b"]


class TestConfidence:
    def test_factors_accumulate(self):
        snapshot = make_snapshot(
            events=(
                event_in_state(
                    "evt_1", EventStatus.COMPLETED, impact=ImpactType.OPPORTUNITY
                ),
            )
        )
        rich = candidate(
            facts=("fact one", "fact two"),
            aligned_principles=("Learn Continuously",),
        )
        confidence = compute_confidence(snapshot, rich)
        assert confidence.factors["strong_fact_pattern"] == 0.2
        assert confidence.factors["principle_alignment"] == 0.15
        assert confidence.factors["historical_support"] == 0.15
        assert confidence.value == 1.0
        assert confidence.level is ConfidenceLevel.HIGH

    def test_untracked_required_resource_lowers_confidence(self):
        needy = candidate(required_energy=20.0)
        confidence = compute_confidence(make_snapshot(), needy)
        assert confidence.factors["untracked_required_resource"] == -0.2
        assert confidence.level is ConfidenceLevel.LOW

    def test_levels_are_thresholded(self):
        base = compute_confidence(make_snapshot(), candidate())
        assert base.value == 0.5
        assert base.level is ConfidenceLevel.MEDIUM
