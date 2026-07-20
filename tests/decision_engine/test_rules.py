"""Each deterministic rule fires on its documented facts and abstains
otherwise (DECISION_ENGINE.md §4 candidate catalog)."""

from paios.domain.enums import EventStatus
from paios.decision_engine.rules import (
    ContinueRunningEventRule,
    HabitReinforcementRule,
    LearningRule,
    ProjectFocusRule,
    ReflectionRule,
    RestRule,
    ResumeSuspendedEventRule,
    default_rules,
)

from tests.decision_engine.conftest import (
    active_project_with_progress,
    energy_resource,
    event_in_state,
    knowledge_gap,
    make_snapshot,
    standard_principles,
    strong_habit,
)


class TestRuleFiring:
    def test_continue_rule_needs_a_running_event(self):
        running = event_in_state("evt_run", EventStatus.STARTED)
        snapshot = make_snapshot(events=(running,), running_event=running)
        (candidate,) = ContinueRunningEventRule().evaluate(snapshot)
        assert candidate.momentum
        assert "evt_run" in candidate.facts[0]
        assert ContinueRunningEventRule().evaluate(make_snapshot()) == ()

    def test_resume_rule_finds_paused_and_interrupted(self):
        snapshot = make_snapshot(
            events=(
                event_in_state("evt_b", EventStatus.INTERRUPTED),
                event_in_state("evt_a", EventStatus.PAUSED),
            )
        )
        candidates = ResumeSuspendedEventRule().evaluate(snapshot)
        assert [c.key for c in candidates] == ["evt_a", "evt_b"]  # sorted
        assert ResumeSuspendedEventRule().evaluate(make_snapshot()) == ()

    def test_rest_rule_fires_below_threshold_only(self):
        low = make_snapshot(
            resources=(energy_resource(10.0),),
            principles=standard_principles(),
        )
        (candidate,) = RestRule().evaluate(low)
        assert candidate.aligned_principles == ("Protect Health",)
        high = make_snapshot(resources=(energy_resource(90.0),))
        assert RestRule().evaluate(high) == ()

    def test_reflection_rule_targets_unreflected_completions(self):
        snapshot = make_snapshot(
            events=(event_in_state("evt_done", EventStatus.COMPLETED),)
        )
        (candidate,) = ReflectionRule().evaluate(snapshot)
        assert candidate.knowledge_growth
        assert ReflectionRule().evaluate(make_snapshot()) == ()

    def test_learning_rule_picks_the_weakest_gap(self):
        snapshot = make_snapshot(
            knowledge=(
                knowledge_gap(confidence=40.0, kid="kno_b"),
                knowledge_gap(confidence=10.0, kid="kno_a"),
            )
        )
        (candidate,) = LearningRule().evaluate(snapshot)
        assert candidate.key == "kno_a"
        confident = make_snapshot(knowledge=(knowledge_gap(confidence=80.0),))
        assert LearningRule().evaluate(confident) == ()

    def test_project_focus_rule_prefers_least_complete_and_goal_aligns(self):
        project, progress, goal = active_project_with_progress(completion=40.0)
        snapshot = make_snapshot(
            projects=(project,), progress=(progress,), goals=(goal,)
        )
        (candidate,) = ProjectFocusRule().evaluate(snapshot)
        assert candidate.goal_aligned
        assert candidate.related_project_id == project.project_id
        assert ProjectFocusRule().evaluate(make_snapshot()) == ()

    def test_habit_rule_reinforces_strongest_only(self):
        snapshot = make_snapshot(habits=(strong_habit(70.0),))
        (candidate,) = HabitReinforcementRule().evaluate(snapshot)
        assert candidate.habit_reinforcing
        weak = make_snapshot(habits=(strong_habit(10.0),))
        assert HabitReinforcementRule().evaluate(weak) == ()

    def test_default_rule_set_is_fixed_and_ordered(self):
        assert [rule.rule_id for rule in default_rules()] == [
            "continue-running-event",
            "resume-suspended-event",
            "rest-on-low-energy",
            "reflect-on-completed",
            "close-knowledge-gap",
            "focus-on-project",
            "reinforce-habit",
        ]
