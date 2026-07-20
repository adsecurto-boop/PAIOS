"""Trend analysis: mandated trend set, both directions, insufficiency."""

from paios.domain.enums import ImpactType
from paios.learning.analyzer import TrendDirection, analyze_trends
from paios.learning.extractor import extract
from paios.learning.history import History

from tests.learning.conftest import (
    completed_event,
    day,
    skipped_event,
    smoking_history,
)


def trend_named(history: History, name: str, as_of=None):
    observations = extract(history, as_of)
    trends = analyze_trends(history, observations)
    return next(trend for trend in trends if trend.name == name)


class TestSmokingAndAlcohol:
    def test_declining_consumption_is_improving(self):
        trend = trend_named(smoking_history(5, 2), "Smoking")
        assert trend.direction is TrendDirection.IMPROVING
        assert trend.first_half == 5.0
        assert trend.second_half == 2.0

    def test_rising_consumption_is_declining(self):
        trend = trend_named(smoking_history(1, 4), "Smoking")
        assert trend.direction is TrendDirection.DECLINING

    def test_no_data_is_insufficient(self):
        history = History(events=(completed_event("evt_1", "study", 1),))
        assert (
            trend_named(history, "Alcohol").direction
            is TrendDirection.INSUFFICIENT_DATA
        )


class TestStudyConsistency:
    def test_more_distinct_days_is_improving(self):
        events = [completed_event("evt_a", "study", 1)]
        events += [
            completed_event(f"evt_b{i}", "study", 8 + i) for i in range(3)
        ]
        events.append(completed_event("evt_anchor", "misc", 14))
        trend = trend_named(History(events=tuple(events)), "Study consistency")
        assert trend.direction is TrendDirection.IMPROVING
        assert trend.first_half == 1.0
        assert trend.second_half == 3.0


class TestFinanceDiscipline:
    def test_smaller_net_loss_is_improving(self):
        events = (
            completed_event("evt_a", "shopping", 1, money_consumed=100.0),
            completed_event("evt_b", "shopping", 10, money_consumed=20.0),
            completed_event("evt_anchor", "misc", 14),
        )
        trend = trend_named(History(events=events), "Finance discipline")
        assert trend.direction is TrendDirection.IMPROVING
        assert trend.first_half == -100.0
        assert trend.second_half == -20.0

    def test_income_counts_positively(self):
        events = (
            completed_event("evt_a", "work", 1, money_produced=50.0),
            completed_event("evt_b", "shopping", 10, money_consumed=500.0),
            completed_event("evt_anchor", "misc", 14),
        )
        trend = trend_named(History(events=events), "Finance discipline")
        assert trend.direction is TrendDirection.DECLINING


class TestDeepWorkQuality:
    def test_longer_sessions_are_improving(self):
        events = (
            completed_event("evt_a", "focus", 1, duration_minutes=30),
            completed_event("evt_b", "focus", 10, duration_minutes=90),
            completed_event("evt_anchor", "misc", 14),
        )
        trend = trend_named(History(events=events), "Deep work quality")
        assert trend.direction is TrendDirection.IMPROVING
        assert trend.first_half == 30.0
        assert trend.second_half == 90.0


class TestScheduleAdherence:
    def test_fewer_skips_is_improving(self):
        events = (
            completed_event("evt_c1", "study", 1),
            skipped_event("evt_s1", "study", 2),
            skipped_event("evt_s2", "study", 3),
            completed_event("evt_c2", "study", 9),
            completed_event("evt_c3", "study", 10),
            completed_event("evt_anchor", "misc", 14),
        )
        trend = trend_named(History(events=events), "Schedule adherence")
        assert trend.direction is TrendDirection.IMPROVING


class TestReflectionCoverage:
    def test_more_reflected_completions_is_improving(self):
        events = (
            completed_event("evt_a", "study", 1),
            completed_event(
                "evt_b", "study", 10, reflection_id="ref_b"
            ),
            completed_event(
                "evt_anchor", "misc", 14, reflection_id="ref_anchor"
            ),
        )
        trend = trend_named(History(events=events), "Reflection coverage")
        assert trend.direction is TrendDirection.IMPROVING
        assert trend.first_half == 0.0
        assert trend.second_half == 1.0
