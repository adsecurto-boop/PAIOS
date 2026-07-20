"""History extraction and pattern detection."""

import pytest

from paios.domain.enums import (
    DisturberType,
    EventOutcomeType,
    EventStatus,
    ImpactType,
)
from paios.learning.analyzer import (
    FindingKind,
    analyze_patterns,
)
from paios.learning.exceptions import InvalidHistoryError
from paios.learning.extractor import extract, reached, resolve_as_of
from paios.learning.history import History

from tests.learning.conftest import (
    completed_event,
    day,
    disturber,
    habit,
    skipped_event,
)


class TestExtraction:
    def test_window_derives_from_the_data_itself(self):
        history = History(
            events=(
                completed_event("evt_1", "study", 0),
                completed_event("evt_2", "study", 10),
            )
        )
        observations = extract(history)
        assert observations.window.start == day(0)
        assert observations.window.end == day(10, 10)  # last end_time

    def test_explicit_as_of_overrides(self):
        history = History(events=(completed_event("evt_1", "study", 0),))
        observations = extract(history, as_of=day(20))
        assert observations.window.end == day(20)

    def test_status_buckets_via_evidence_trail(self):
        history = History(
            events=(
                completed_event("evt_done", "study", 1),
                skipped_event("evt_skip", "study", 2),
            )
        )
        observations = extract(history)
        assert len(observations.completed) == 1
        assert len(observations.skipped) == 1

    def test_archived_events_still_count_as_what_they_were(self):
        event = completed_event("evt_1", "study", 1)
        event.transition_to(EventStatus.ARCHIVED, day(5))
        observations = extract(History(events=(event,)))
        assert len(observations.completed) == 1
        assert reached(event, EventStatus.COMPLETED)

    def test_empty_history_resolves_to_nothing(self):
        observations = extract(History())
        assert observations.window is None
        assert resolve_as_of(History(), None) is None

    def test_categories_are_sorted_and_normalized(self):
        history = History(
            events=(
                completed_event("evt_1", "Study", 1),
                completed_event("evt_2", "smoking", 2),
            )
        )
        assert extract(history).categories == ("smoking", "study")

    def test_invalid_input_rejected(self):
        with pytest.raises(InvalidHistoryError):
            extract({"not": "history"})

    def test_half_split_is_deterministic(self):
        history = History(
            events=(
                completed_event("evt_a", "study", 1),
                completed_event("evt_b", "study", 13),
            )
        )
        observations = extract(history, as_of=day(14))
        first, second = observations.split_halves(observations.completed)
        assert [str(e.event_id) for e in first] == ["evt_a"]
        assert [str(e.event_id) for e in second] == ["evt_b"]


class TestPatternDetection:
    def test_repeated_failures_detected(self):
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
        findings = analyze_patterns(history, extract(history))
        (finding,) = [
            f for f in findings if f.kind is FindingKind.REPEATED_FAILURE
        ]
        assert finding.category == "study"
        assert finding.count == 3
        assert len(finding.evidence) == 3

    def test_below_threshold_is_silent(self):
        history = History(
            events=tuple(
                completed_event(
                    f"evt_{i}", "study", i, outcome=EventOutcomeType.FAILED
                )
                for i in range(2)
            )
        )
        assert analyze_patterns(history, extract(history)) == ()

    def test_repeated_successes_detected(self):
        history = History(
            events=tuple(
                completed_event(
                    f"evt_{i}",
                    "exercise",
                    i,
                    outcome=EventOutcomeType.COMPLETED,
                )
                for i in range(4)
            )
        )
        findings = analyze_patterns(history, extract(history))
        (finding,) = [
            f for f in findings if f.kind is FindingKind.REPEATED_SUCCESS
        ]
        assert finding.count == 4

    def test_repeated_distractions_detected(self):
        history = History(
            events=tuple(
                completed_event(
                    f"evt_{i}", "doomscrolling", i, impact=ImpactType.DISTRACTION
                )
                for i in range(3)
            )
        )
        findings = analyze_patterns(history, extract(history))
        (finding,) = [
            f for f in findings if f.kind is FindingKind.REPEATED_DISTRACTION
        ]
        assert finding.category == "doomscrolling"

    def test_reward_misuse_detected(self):
        history = History(
            events=tuple(
                completed_event(
                    f"evt_{i}", "gaming", i, impact=ImpactType.DISTRACTION
                )
                for i in range(3)
            ),
            habits=(habit("gaming", reward="relaxation"),),
        )
        findings = analyze_patterns(history, extract(history))
        assert any(
            f.kind is FindingKind.REWARD_MISUSE and "relaxation" in f.description
            for f in findings
        )

    def test_frequent_disturbances_detected(self):
        history = History(
            events=(completed_event("evt_1", "study", 5),),
            event_disturbers=tuple(
                disturber(f"dist_{i}", DisturberType.WORK, i) for i in range(3)
            ),
        )
        findings = analyze_patterns(history, extract(history))
        (finding,) = [
            f for f in findings if f.kind is FindingKind.FREQUENT_DISTURBANCE
        ]
        assert finding.category == "work"
        assert finding.count == 3
