"""Plan immutability (refinement 2) and the Planner interface (refinement 3)."""

from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from paios.domain.value_objects.identifiers import EventId
from paios.scheduler.exceptions import SchedulingConflictError
from paios.scheduler.plan import PlanEntry, SchedulingPlan
from paios.scheduler.planner import (
    DEFAULT_SLOT_MINUTES,
    DeterministicPlanner,
    PlanCandidate,
    Planner,
)

from tests.scheduler.conftest import T0, at, seed_context


def entry(event_id: str, start: datetime, minutes: int = 60, priority: float = 0):
    return PlanEntry(
        event_id=EventId(event_id),
        planned_start=start,
        duration_minutes=minutes,
        priority=priority,
    )


class TestPlanImmutability:
    def test_entries_are_frozen_and_id_only(self):
        plan_entry = entry("evt_1", T0)
        with pytest.raises(FrozenInstanceError):
            plan_entry.planned_start = at(10)
        assert isinstance(plan_entry.event_id, EventId)

    def test_plan_is_frozen(self):
        plan = SchedulingPlan(created_at=T0, entries=(entry("evt_1", T0),))
        with pytest.raises(FrozenInstanceError):
            plan.created_at = at(1)

    def test_overlapping_entries_rejected(self):
        with pytest.raises(SchedulingConflictError):
            SchedulingPlan(
                created_at=T0,
                entries=(entry("evt_1", T0, 60), entry("evt_2", at(30), 60)),
            )

    def test_entries_sorted_by_start(self):
        plan = SchedulingPlan(
            created_at=T0,
            entries=(entry("evt_2", at(120)), entry("evt_1", T0)),
        )
        assert [str(e.event_id) for e in plan.entries] == ["evt_1", "evt_2"]

    def test_helpers(self):
        plan = SchedulingPlan(
            created_at=T0,
            entries=(entry("evt_1", T0), entry("evt_2", at(120))),
        )
        assert plan.entry_for(EventId("evt_2")).planned_start == at(120)
        assert plan.entry_for(EventId("missing")) is None
        assert plan.next_entry(at(60)).event_id == EventId("evt_2")
        assert plan.without(EventId("evt_1")).entries[0].event_id == EventId(
            "evt_2"
        )


class TestDeterministicPlanner:
    def make_candidates(self):
        return (
            PlanCandidate(EventId("evt_low"), 1.0, T0),
            PlanCandidate(EventId("evt_high"), 9.0, T0),
            PlanCandidate(EventId("evt_mid"), 5.0, T0),
        )

    def test_priority_ordering(self):
        plan = DeterministicPlanner().plan(T0, self.make_candidates())
        assert [str(e.event_id) for e in plan.entries] == [
            "evt_high",
            "evt_mid",
            "evt_low",
        ]

    def test_sequential_non_overlapping_slots(self):
        plan = DeterministicPlanner().plan(T0, self.make_candidates())
        first, second, third = plan.entries
        assert first.planned_start == T0
        assert second.planned_start == first.planned_end
        assert third.planned_start == second.planned_end
        assert first.duration_minutes == DEFAULT_SLOT_MINUTES

    def test_earliest_start_respected(self):
        plan = DeterministicPlanner().plan(
            T0, (PlanCandidate(EventId("evt_1"), 5.0, at(90)),)
        )
        assert plan.entries[0].planned_start == at(90)

    def test_never_plans_in_the_past(self):
        plan = DeterministicPlanner().plan(
            at(60), (PlanCandidate(EventId("evt_1"), 5.0, T0),)
        )
        assert plan.entries[0].planned_start == at(60)

    def test_deterministic(self):
        first = DeterministicPlanner().plan(T0, self.make_candidates())
        second = DeterministicPlanner().plan(T0, self.make_candidates())
        assert first == second


class TestPlannerInterface:
    def test_scheduler_uses_injected_planner(self, system):
        class StubPlanner(Planner):
            def __init__(self):
                self.calls = 0

            def plan(self, current_time, candidates):
                self.calls += 1
                return SchedulingPlan(created_at=current_time, entries=())

        stub = StubPlanner()
        wired = system(seed=seed_context, planner=stub)
        assert stub.calls >= 1
        assert wired.scheduler.plan.is_empty
