"""Domain invariant catalog and cross-aggregate domain-service checks."""

import pytest

from paios.domain.enums import EventStatus
from paios.domain.errors import InvariantViolationError
from paios.domain.services.invariants import (
    DOMAIN_INVARIANTS,
    InvariantScope,
    ensure_at_most_one_running_user_event,
    ensure_single_active_context_window,
    ensure_unique_context_window_ownership,
    find_running_event,
)

from tests.domain.conftest import T0, at


def start(event) -> None:
    event.transition_to(EventStatus.SCHEDULED, at(1))
    event.transition_to(EventStatus.READY, at(2))
    event.transition_to(EventStatus.STARTED, at(3))


class TestInvariantCatalog:
    def test_all_business_rules_invariants_are_defined(self):
        names = {invariant.name for invariant in DOMAIN_INVARIANTS}
        assert names == {
            "single-active-context-window",
            "single-running-event",
            "completed-events-immutable",
            "recommendations-never-modify-events",
            "resources-cannot-become-invalid",
            "reflection-requires-event",
            "progress-belongs-to-one-project",
            "context-window-references-one-context",
            "scheduler-never-edits-history",
            "event-ids-immutable",
            "one-scheduler-per-user",
            "event-owns-one-context-window",
            "disturber-never-references-event-mutable-fields",
            "principles-never-altered-by-decision-engine",
        }

    def test_runtime_kernel_invariants_are_defined_but_deferred(self):
        deferred = [
            invariant
            for invariant in DOMAIN_INVARIANTS
            if invariant.scope is InvariantScope.RUNTIME_KERNEL
        ]
        assert deferred, "Runtime Kernel invariants must be defined in Milestone 1"
        assert all(not inv.enforced_in_milestone_1 for inv in deferred)

    def test_running_event_invariant_is_not_weakened(self):
        invariant = next(
            inv for inv in DOMAIN_INVARIANTS if inv.name == "single-running-event"
        )
        assert "Exactly one" in invariant.description
        assert "Idle" in (invariant.notes or "")


class TestActiveContextWindowCheck:
    def test_zero_or_one_active_passes(self, make_window):
        created = make_window("win_001", event_id="evt_001")
        active = make_window("win_002", event_id="evt_002")
        active.activate(T0)
        assert ensure_single_active_context_window([created]) is None
        assert ensure_single_active_context_window([created, active]) is active

    def test_two_active_windows_violate_invariant(self, make_window):
        first = make_window("win_001", event_id="evt_001")
        second = make_window("win_002", event_id="evt_002")
        first.activate(T0)
        second.activate(at(1))
        with pytest.raises(InvariantViolationError):
            ensure_single_active_context_window([first, second])


class TestRunningEventCheck:
    def test_at_most_one_running_user_event(self, make_event):
        idle_side = make_event("evt_001", context_window_id="win_001")
        running = make_event("evt_002", context_window_id="win_002")
        start(running)
        assert ensure_at_most_one_running_user_event([idle_side, running]) is running
        assert find_running_event([idle_side]) is None

    def test_two_running_events_violate_invariant(self, make_event):
        first = make_event("evt_001", context_window_id="win_001")
        second = make_event("evt_002", context_window_id="win_002")
        start(first)
        start(second)
        with pytest.raises(InvariantViolationError):
            ensure_at_most_one_running_user_event([first, second])

    def test_resumed_counts_as_running(self, make_event):
        event = make_event()
        start(event)
        event.transition_to(EventStatus.PAUSED, at(4))
        event.transition_to(EventStatus.RESUMED, at(5))
        assert find_running_event([event]) is event


class TestContextWindowOwnershipCheck:
    def test_unique_ownership_passes(self, make_event):
        events = [
            make_event("evt_001", context_window_id="win_001"),
            make_event("evt_002", context_window_id="win_002"),
        ]
        ensure_unique_context_window_ownership(events)

    def test_shared_window_violates_invariant(self, make_event):
        events = [
            make_event("evt_001", context_window_id="win_001"),
            make_event("evt_002", context_window_id="win_001"),
        ]
        with pytest.raises(InvariantViolationError):
            ensure_unique_context_window_ownership(events)
