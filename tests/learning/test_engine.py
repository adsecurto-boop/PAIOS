"""The Learning Engine: determinism, purity, replay, summaries, scale."""

from paios.domain.enums import EventOutcomeType, ImpactType
from paios.learning.history import History, HistoryLoader
from paios.learning.learning_engine import LearningEngine

from tests.learning.conftest import (
    T0,
    completed_event,
    day,
    habit,
    reflection,
    skipped_event,
    smoking_history,
)


def rich_history() -> History:
    events = list(smoking_history().events)
    events += [
        completed_event(
            f"evt_study_{i}",
            "study",
            2 + i,
            impact=ImpactType.OPPORTUNITY,
            outcome=EventOutcomeType.COMPLETED,
        )
        for i in range(4)
    ]
    events.append(skipped_event("evt_skip", "study", 6))
    return History(
        events=tuple(events),
        reflections=(reflection("ref_1", "evt_study_0", 3),),
        habits=(habit("study", habit_id="hab_study"),),
    )


class TestDeterminism:
    def test_identical_history_identical_result(self):
        first = LearningEngine().learn(rich_history())
        second = LearningEngine().learn(rich_history())
        assert first == second  # full deep equality, insight IDs included

    def test_repeated_learning_on_one_engine_is_stateless(self):
        engine = LearningEngine()
        history = rich_history()
        assert engine.learn(history) == engine.learn(history)
        assert engine.learn(History()).generated_at is None


class TestPurity:
    def test_learning_mutates_nothing(self):
        history = rich_history()
        transition_counts = [len(e.transitions) for e in history.events]
        statuses = [e.status for e in history.events]
        habit_strengths = [h.strength for h in history.habits]
        LearningEngine().learn(history)
        assert [len(e.transitions) for e in history.events] == transition_counts
        assert [e.status for e in history.events] == statuses
        assert [h.strength for h in history.habits] == habit_strengths


class TestEdgeCases:
    def test_empty_history_is_a_quiet_result(self):
        result = LearningEngine().learn(History())
        assert result.generated_at is None
        assert result.findings == ()
        assert result.insights == ()
        assert result.weekly_summary is None
        assert result.monthly_summary is None
        assert result.learning_report.events_observed == 0

    def test_as_of_override_controls_the_window(self):
        history = History(events=(completed_event("evt_1", "study", 0),))
        result = LearningEngine().learn(history, as_of=day(30))
        assert result.generated_at == day(30)


class TestSummaries:
    def test_weekly_summary_counts_only_the_last_seven_days(self):
        history = History(
            events=(
                completed_event(
                    "evt_old", "study", 0, impact=ImpactType.OPPORTUNITY
                ),
                completed_event(
                    "evt_recent",
                    "study",
                    13,
                    impact=ImpactType.OPPORTUNITY,
                    duration_minutes=90,
                ),
                completed_event(
                    "evt_waste",
                    "doomscrolling",
                    13,
                    impact=ImpactType.DISTRACTION,
                    duration_minutes=30,
                ),
            )
        )
        result = LearningEngine().learn(history, as_of=day(14))
        weekly = result.weekly_summary
        assert weekly.completed == 2
        assert weekly.opportunity_minutes == 90
        assert weekly.distraction_minutes == 30
        monthly = result.monthly_summary
        assert monthly.completed == 3

    def test_top_category_is_deterministic(self):
        history = History(
            events=(
                completed_event("evt_1", "study", 13),
                completed_event("evt_2", "study", 13, duration_minutes=30),
                completed_event("evt_3", "exercise", 13),
            )
        )
        result = LearningEngine().learn(history, as_of=day(14))
        assert result.weekly_summary.top_category == "study"


class TestReplayConsistency:
    def test_learning_over_reloaded_history_is_identical(self, tmp_path):
        from paios.repositories.factory import RepositoryFactory

        factory = RepositoryFactory(tmp_path / "data")
        factory.initialize()
        for event in rich_history().events:
            factory.events().save(event)
        for item in rich_history().reflections:
            factory.reflections().save(item)
        for item in rich_history().habits:
            factory.habits().save(item)

        loader = HistoryLoader(factory)
        first = LearningEngine().learn(loader.load())
        second = LearningEngine().learn(loader.load())
        assert first == second
        assert first.learning_report.events_observed == len(
            rich_history().events
        )


class TestScale:
    def test_two_hundred_event_history(self):
        events = tuple(
            completed_event(
                f"evt_{i:03d}",
                "study" if i % 2 else "focus",
                i % 30,
                impact=(
                    ImpactType.OPPORTUNITY if i % 3 else ImpactType.DISTRACTION
                ),
            )
            for i in range(200)
        )
        result = LearningEngine().learn(History(events=events))
        assert result.learning_report.completed == 200
        assert result.trends
        assert result.candidate_habit_changes  # repeated untracked categories
