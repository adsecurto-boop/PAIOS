"""Insight generation, Candidate Principles, Candidate Habit Changes."""

from paios.domain.enums import (
    EventOutcomeType,
    ImpactType,
    PrincipleCategory,
)
from paios.learning.analyzer import analyze_patterns
from paios.learning.extractor import extract
from paios.learning.habit_analyzer import (
    HabitChangeAction,
    propose_habit_changes,
)
from paios.learning.history import History
from paios.learning.principle_generator import propose_principles
from paios.learning.reflection_engine import analyze_reflections

from tests.learning.conftest import (
    completed_event,
    day,
    habit,
    principle,
    reflection,
    smoking_history,
)


class TestInsights:
    def test_one_insight_per_reflection_with_a_lesson(self):
        history = History(
            events=(completed_event("evt_1", "study", 1),),
            reflections=(
                reflection("ref_1", "evt_1", 2),
                reflection("ref_2", "evt_1", 3, lesson=None),
            ),
        )
        insights, quality = analyze_reflections(history)
        assert len(insights) == 1
        assert str(insights[0].source_reflection_id) == "ref_1"
        assert quality.total == 2
        assert quality.with_lesson == 1

    def test_insight_ids_are_deterministic(self):
        history = History(
            events=(completed_event("evt_1", "study", 1),),
            reflections=(reflection("ref_1", "evt_1", 2),),
        )
        first, _ = analyze_reflections(history)
        second, _ = analyze_reflections(history)
        assert first[0].insight_id == second[0].insight_id

    def test_insight_category_comes_from_the_reflected_event(self):
        history = History(
            events=(completed_event("evt_1", "exercise", 1),),
            reflections=(reflection("ref_1", "evt_1", 2),),
        )
        insights, _ = analyze_reflections(history)
        assert insights[0].category == "exercise"

    def test_reusable_requires_root_cause_and_lesson(self):
        history = History(
            events=(completed_event("evt_1", "study", 1),),
            reflections=(
                reflection("ref_full", "evt_1", 2),
                reflection("ref_thin", "evt_1", 3, root_cause=None),
            ),
        )
        insights, quality = analyze_reflections(history)
        by_source = {
            str(insight.source_reflection_id): insight for insight in insights
        }
        assert by_source["ref_full"].reusable
        assert not by_source["ref_thin"].reusable
        assert quality.complete == 1

    def test_insight_timestamps_come_from_the_reflection(self):
        history = History(
            events=(completed_event("evt_1", "study", 1),),
            reflections=(reflection("ref_1", "evt_1", 5),),
        )
        insights, _ = analyze_reflections(history)
        assert insights[0].created_at == day(5)


class TestCandidatePrinciples:
    def test_smoking_history_yields_health_candidate(self):
        history = smoking_history()
        observations = extract(history)
        findings = analyze_patterns(history, observations)
        candidates = propose_principles(history, observations, findings)
        (candidate,) = [c for c in candidates if c.name == "Reduce Smoking"]
        assert candidate.category is PrincipleCategory.HEALTH
        assert len(candidate.evidence) >= 3

    def test_existing_principle_suppresses_the_candidate(self):
        base = smoking_history()
        history = History(
            events=base.events,
            principles=(principle("Reduce Smoking", PrincipleCategory.HEALTH),),
        )
        observations = extract(history)
        findings = analyze_patterns(history, observations)
        candidates = propose_principles(history, observations, findings)
        assert not any(c.name == "Reduce Smoking" for c in candidates)

    def test_net_money_loss_yields_resources_candidate(self):
        history = History(
            events=tuple(
                completed_event(
                    f"evt_{i}", "shopping", i, money_consumed=50.0
                )
                for i in range(3)
            )
        )
        observations = extract(history)
        candidates = propose_principles(history, observations, ())
        assert any(c.name == "Guard Spending" for c in candidates)

    def test_repeated_study_failures_yield_learning_candidate(self):
        history = History(
            events=tuple(
                completed_event(
                    f"evt_{i}",
                    "study",
                    i,
                    outcome=EventOutcomeType.FAILED,
                )
                for i in range(3)
            )
        )
        observations = extract(history)
        findings = analyze_patterns(history, observations)
        candidates = propose_principles(history, observations, findings)
        assert any(c.name == "Prepare Before Studying" for c in candidates)


class TestCandidateHabitChanges:
    def test_untracked_repeated_category_yields_create(self):
        history = History(
            events=tuple(
                completed_event(f"evt_{i}", "exercise", i) for i in range(3)
            )
        )
        observations = extract(history)
        proposals = propose_habit_changes(history, observations, ())
        (proposal,) = proposals
        assert proposal.action is HabitChangeAction.CREATE
        assert proposal.name == "exercise"
        assert proposal.habit_id is None

    def test_opportunity_majority_yields_reinforce(self):
        history = History(
            events=tuple(
                completed_event(
                    f"evt_{i}", "exercise", i, impact=ImpactType.OPPORTUNITY
                )
                for i in range(3)
            ),
            habits=(habit("exercise"),),
        )
        observations = extract(history)
        proposals = propose_habit_changes(history, observations, ())
        (proposal,) = proposals
        assert proposal.action is HabitChangeAction.REINFORCE
        assert proposal.habit_id is not None

    def test_distraction_majority_yields_weaken(self):
        history = History(
            events=tuple(
                completed_event(
                    f"evt_{i}", "gaming", i, impact=ImpactType.DISTRACTION
                )
                for i in range(3)
            ),
            habits=(habit("gaming", reward="fun"),),
        )
        observations = extract(history)
        findings = analyze_patterns(history, observations)
        proposals = propose_habit_changes(history, observations, findings)
        (proposal,) = proposals
        assert proposal.action is HabitChangeAction.WEAKEN
        assert "reward" in proposal.rationale

    def test_tracked_category_never_double_proposed_as_create(self):
        history = History(
            events=tuple(
                completed_event(
                    f"evt_{i}", "exercise", i, impact=ImpactType.OPPORTUNITY
                )
                for i in range(3)
            ),
            habits=(habit("exercise"),),
        )
        observations = extract(history)
        proposals = propose_habit_changes(history, observations, ())
        assert all(
            proposal.action is not HabitChangeAction.CREATE
            for proposal in proposals
        )
