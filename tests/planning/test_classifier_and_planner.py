"""Classifier determinism and MetadataPlanner behavior (M20)."""

from datetime import datetime, timedelta

from paios.domain.value_objects.identifiers import EventId, RecommendationId
from paios.planning.classifier import classify_lines
from paios.planning.metadata_planner import MetadataPlanner
from paios.planning.stores import EventMetadataStore
from paios.scheduler.planner import DeterministicPlanner, PlanCandidate

T0 = datetime(2026, 7, 22, 9, 0)

CAPTURE = """Tomorrow
Temple
Study ISTQB
Gym
Buy medicine
Build PAIOS
Become a better public speaker over the coming year
"""


class TestClassifier:
    def test_day_header_scopes_following_lines(self):
        lines = classify_lines(CAPTURE)
        header, *items = lines
        assert header.kind == "day_header"
        assert all(item.day_scope == "tomorrow" for item in items)

    def test_kinds_are_deterministic_and_sensible(self):
        by_text = {line.text: line.kind for line in classify_lines(CAPTURE)}
        assert by_text["Temple"] == "event"
        assert by_text["Gym"] == "event"
        assert by_text["Buy medicine"] == "event"
        assert by_text["Build PAIOS"] == "project"
        assert (
            by_text["Become a better public speaker over the coming year"]
            == "goal"
        )

    def test_duplicate_and_similar_detection(self):
        lines = classify_lines(
            "Buy medicine\nStudy ISTQB syllabus",
            existing_events=("Buy medicine", "Study ISTQB chapter 2"),
        )
        assert lines[0].duplicate_of == "Buy medicine"
        assert "Study ISTQB chapter 2" in lines[1].similar_to

    def test_identical_input_identical_output(self):
        assert classify_lines(CAPTURE) == classify_lines(CAPTURE)


def candidate(event_id: str, priority: float = 1.0, rec: str | None = None):
    return PlanCandidate(
        event_id=EventId(event_id),
        priority=priority,
        earliest_start=T0,
        recommendation_id=RecommendationId(rec) if rec else None,
    )


class TestMetadataPlanner:
    def test_without_metadata_matches_deterministic_planner(self, tmp_path):
        candidates = (candidate("e1", 2.0), candidate("e2", 1.0))
        with_metadata = MetadataPlanner(EventMetadataStore(tmp_path)).plan(
            T0, candidates
        )
        baseline = DeterministicPlanner().plan(T0, candidates)
        assert [e.event_id for e in with_metadata.entries] == [
            e.event_id for e in baseline.entries
        ]
        assert [e.duration_minutes for e in with_metadata.entries] == [
            e.duration_minutes for e in baseline.entries
        ]

    def test_estimated_duration_applies(self, tmp_path):
        store = EventMetadataStore(tmp_path)
        store.set("e1", {"estimated_duration_minutes": 25}, T0)
        plan = MetadataPlanner(store).plan(
            T0, (candidate("e1"), candidate("e2"))
        )
        first, second = plan.entries
        assert first.duration_minutes == 25
        assert second.planned_start == first.planned_start + timedelta(
            minutes=25
        )

    def test_duration_resolves_via_recommendation_key(self, tmp_path):
        store = EventMetadataStore(tmp_path)
        store.set("r1", {"estimated_duration_minutes": 15}, T0)
        plan = MetadataPlanner(store).plan(
            T0, (candidate("e1", rec="r1"),)
        )
        assert plan.entries[0].duration_minutes == 15

    def test_deadline_orders_within_equal_priority(self, tmp_path):
        store = EventMetadataStore(tmp_path)
        store.set("e2", {"deadline": "2026-07-22T12:00:00"}, T0)
        plan = MetadataPlanner(store).plan(
            T0, (candidate("e1"), candidate("e2"))
        )
        assert str(plan.entries[0].event_id) == "e2"

    def test_priority_still_dominates_deadline(self, tmp_path):
        store = EventMetadataStore(tmp_path)
        store.set("e2", {"deadline": "2026-07-22T12:00:00"}, T0)
        plan = MetadataPlanner(store).plan(
            T0, (candidate("e1", 5.0), candidate("e2", 1.0))
        )
        assert str(plan.entries[0].event_id) == "e1"

    def test_dependency_defers_dependent(self, tmp_path):
        store = EventMetadataStore(tmp_path)
        # e1 outranks e2 but depends on it -> must slot after it.
        store.set("e1", {"depends_on": ["e2"]}, T0)
        plan = MetadataPlanner(store).plan(
            T0, (candidate("e1", 5.0), candidate("e2", 1.0))
        )
        assert [str(e.event_id) for e in plan.entries] == ["e2", "e1"]

    def test_absent_prerequisite_constrains_nothing(self, tmp_path):
        store = EventMetadataStore(tmp_path)
        store.set("e1", {"depends_on": ["gone"]}, T0)
        plan = MetadataPlanner(store).plan(T0, (candidate("e1", 5.0),))
        assert [str(e.event_id) for e in plan.entries] == ["e1"]

    def test_dependency_cycle_is_harmless(self, tmp_path):
        store = EventMetadataStore(tmp_path)
        store.set("e1", {"depends_on": ["e2"]}, T0)
        store.set("e2", {"depends_on": ["e1"]}, T0)
        plan = MetadataPlanner(store).plan(
            T0, (candidate("e1", 2.0), candidate("e2", 1.0))
        )
        assert len(plan.entries) == 2  # both planned, no hang

    def test_plan_is_overlap_free_and_future_only(self, tmp_path):
        store = EventMetadataStore(tmp_path)
        store.set("e1", {"estimated_duration_minutes": 90}, T0)
        plan = MetadataPlanner(store).plan(
            T0, tuple(candidate(f"e{i}") for i in range(1, 5))
        )
        for earlier, later in zip(plan.entries, plan.entries[1:]):
            assert later.planned_start >= earlier.planned_end
            assert earlier.planned_start >= T0
