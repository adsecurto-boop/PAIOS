"""Event aggregate: canonical lifecycle, immutability, outcome evidence.

Valid and invalid transitions asserted here are transcribed from
STATE_MACHINES.md section 1 (formal transitions and "Invalid transitions").
"""

import pytest

from paios.domain.entities.event import Event
from paios.domain.enums import EventOutcomeType, EventStatus
from paios.domain.errors import (
    DomainValidationError,
    ImmutabilityViolationError,
    InvalidTransitionError,
)
from paios.domain.value_objects.event_outcome import EventOutcome
from paios.domain.value_objects.identifiers import EventId, ReflectionId

from tests.domain.conftest import T0, at


def advance(event: Event, *states: EventStatus) -> None:
    for offset, state in enumerate(states, start=1):
        event.transition_to(state, at(offset))


class TestEventCreation:
    def test_initial_state_is_recommended(self, make_event):
        event = make_event()
        assert event.status is EventStatus.RECOMMENDED
        assert event.transitions == ()

    def test_requires_category_and_description(self, make_event):
        with pytest.raises(DomainValidationError):
            make_event(category="   ")
        with pytest.raises(DomainValidationError):
            make_event(description="")

    def test_equality_is_by_identity(self, make_event):
        assert make_event("evt_001") == make_event("evt_001")
        assert make_event("evt_001") != make_event("evt_002")


class TestEventLifecycle:
    def test_full_happy_path_to_archived(self, make_event):
        event = make_event()
        advance(
            event,
            EventStatus.SCHEDULED,
            EventStatus.READY,
            EventStatus.STARTED,
            EventStatus.COMPLETED,
            EventStatus.ARCHIVED,
        )
        assert event.status is EventStatus.ARCHIVED
        assert [record.to_state for record in event.transitions] == [
            EventStatus.SCHEDULED,
            EventStatus.READY,
            EventStatus.STARTED,
            EventStatus.COMPLETED,
            EventStatus.ARCHIVED,
        ]

    def test_pause_resume_cycle(self, make_event):
        event = make_event()
        advance(
            event,
            EventStatus.SCHEDULED,
            EventStatus.READY,
            EventStatus.STARTED,
            EventStatus.PAUSED,
            EventStatus.RESUMED,
            EventStatus.STARTED,
            EventStatus.COMPLETED,
        )
        assert event.status is EventStatus.COMPLETED

    def test_resumed_may_complete_directly(self, make_event):
        event = make_event()
        advance(
            event,
            EventStatus.SCHEDULED,
            EventStatus.READY,
            EventStatus.STARTED,
            EventStatus.PAUSED,
            EventStatus.RESUMED,
            EventStatus.COMPLETED,
        )
        assert event.status is EventStatus.COMPLETED

    def test_interruption_paths(self, make_event):
        resumed = make_event("evt_r")
        advance(
            resumed,
            EventStatus.SCHEDULED,
            EventStatus.READY,
            EventStatus.STARTED,
            EventStatus.INTERRUPTED,
            EventStatus.RESUMED,
        )
        assert resumed.status is EventStatus.RESUMED

        cancelled = make_event("evt_c")
        advance(
            cancelled,
            EventStatus.SCHEDULED,
            EventStatus.READY,
            EventStatus.STARTED,
            EventStatus.INTERRUPTED,
            EventStatus.CANCELLED,
        )
        assert cancelled.status is EventStatus.CANCELLED

        overtaken = make_event("evt_o")
        advance(
            overtaken,
            EventStatus.SCHEDULED,
            EventStatus.READY,
            EventStatus.STARTED,
            EventStatus.INTERRUPTED,
            EventStatus.OVERTAKEN,
        )
        assert overtaken.status is EventStatus.OVERTAKEN

    def test_scheduled_terminal_alternatives(self, make_event):
        for target in (
            EventStatus.SKIPPED,
            EventStatus.CANCELLED,
            EventStatus.OVERTAKEN,
        ):
            event = make_event(f"evt_{target.value}")
            advance(event, EventStatus.SCHEDULED, target)
            assert event.status is target

    def test_running_is_started_or_resumed_only(self, make_event):
        event = make_event()
        assert not event.is_running
        advance(event, EventStatus.SCHEDULED, EventStatus.READY, EventStatus.STARTED)
        assert event.is_running
        event.transition_to(EventStatus.PAUSED, at(4))
        assert not event.is_running
        event.transition_to(EventStatus.RESUMED, at(5))
        assert event.is_running

    def test_actor_defaults_to_scheduler(self, make_event):
        event = make_event()
        record = event.transition_to(EventStatus.SCHEDULED, T0)
        assert record.actor == "Scheduler"


class TestInvalidTransitions:
    """The explicit invalid transitions of STATE_MACHINES.md section 1."""

    def test_recommended_cannot_start_or_complete(self, make_event):
        for target in (EventStatus.STARTED, EventStatus.COMPLETED):
            with pytest.raises(InvalidTransitionError):
                make_event().transition_to(target, T0)

    def test_scheduled_is_not_proof_of_action(self, make_event):
        event = make_event()
        event.transition_to(EventStatus.SCHEDULED, T0)
        with pytest.raises(InvalidTransitionError):
            event.transition_to(EventStatus.COMPLETED, at(1))

    def test_completed_history_cannot_reopen(self, make_event):
        event = make_event()
        advance(
            event,
            EventStatus.SCHEDULED,
            EventStatus.READY,
            EventStatus.STARTED,
            EventStatus.COMPLETED,
        )
        for target in (
            EventStatus.STARTED,
            EventStatus.READY,
            EventStatus.SCHEDULED,
            EventStatus.RESUMED,
        ):
            with pytest.raises(InvalidTransitionError):
                event.transition_to(target, at(10))

    def test_terminal_states_cannot_return_to_ready(self, make_event):
        skipped = make_event("evt_s")
        advance(skipped, EventStatus.SCHEDULED, EventStatus.SKIPPED)
        with pytest.raises(InvalidTransitionError):
            skipped.transition_to(EventStatus.READY, at(3))

        overtaken = make_event("evt_o")
        advance(overtaken, EventStatus.SCHEDULED, EventStatus.OVERTAKEN)
        with pytest.raises(InvalidTransitionError):
            overtaken.transition_to(EventStatus.READY, at(3))

    def test_only_completed_skipped_cancelled_archive(self, make_event):
        overtaken = make_event()
        advance(overtaken, EventStatus.SCHEDULED, EventStatus.OVERTAKEN)
        with pytest.raises(InvalidTransitionError):
            overtaken.transition_to(EventStatus.ARCHIVED, at(3))


class TestEventImmutability:
    def test_event_id_immutable_once_assigned(self, make_event):
        event = make_event()
        with pytest.raises(ImmutabilityViolationError):
            event.event_id = EventId("evt_999")

    def test_transition_history_cannot_be_replaced(self, make_event):
        from paios.domain.enums import EventStatus as ES
        from paios.domain.state_machines.definitions import EVENT_STATE_MACHINE
        from paios.domain.state_machines.machine import TransitionHistory

        event = make_event()
        with pytest.raises(ImmutabilityViolationError):
            event._history = TransitionHistory(EVENT_STATE_MACHINE, ES.RECOMMENDED)

    def test_facts_mutable_before_execution_ends(self, make_event):
        event = make_event()
        event.actual_outcome = "Completed chapter 3, took notes"
        assert event.actual_outcome == "Completed chapter 3, took notes"

    def test_completed_event_facts_are_frozen(self, make_event):
        event = make_event()
        advance(
            event,
            EventStatus.SCHEDULED,
            EventStatus.READY,
            EventStatus.STARTED,
            EventStatus.COMPLETED,
        )
        with pytest.raises(ImmutabilityViolationError):
            event.description = "rewritten history"
        with pytest.raises(ImmutabilityViolationError):
            event.actual_outcome = "rewritten outcome"

    def test_cancelled_event_facts_are_frozen_too(self, make_event):
        event = make_event()
        advance(event, EventStatus.SCHEDULED, EventStatus.CANCELLED)
        with pytest.raises(ImmutabilityViolationError):
            event.category = "rewritten"

    def test_priority_alignment_score_bounds(self, make_event):
        event = make_event()
        event.priority_alignment_score = 9
        with pytest.raises(DomainValidationError):
            event.priority_alignment_score = 11
        with pytest.raises(DomainValidationError):
            event.priority_alignment_score = -1


class TestEventOutcomeEvidence:
    def test_outcome_recorded_once_after_completion(self, make_event):
        event = make_event()
        advance(
            event,
            EventStatus.SCHEDULED,
            EventStatus.READY,
            EventStatus.STARTED,
            EventStatus.COMPLETED,
        )
        event.record_outcome(EventOutcome(EventOutcomeType.COMPLETED, at(5)))
        assert event.outcome.outcome_type is EventOutcomeType.COMPLETED
        with pytest.raises(ImmutabilityViolationError):
            event.record_outcome(EventOutcome(EventOutcomeType.PARTIAL, at(6)))

    def test_interrupted_then_cancelled_may_record_partial(self, make_event):
        event = make_event()
        advance(
            event,
            EventStatus.SCHEDULED,
            EventStatus.READY,
            EventStatus.STARTED,
            EventStatus.INTERRUPTED,
            EventStatus.CANCELLED,
        )
        event.record_outcome(
            EventOutcome(EventOutcomeType.PARTIAL, at(6), note="stopped mid-way")
        )
        assert event.outcome.outcome_type is EventOutcomeType.PARTIAL

    def test_outcome_rejected_while_running_or_skipped(self, make_event):
        running = make_event("evt_run")
        advance(
            running, EventStatus.SCHEDULED, EventStatus.READY, EventStatus.STARTED
        )
        with pytest.raises(DomainValidationError):
            running.record_outcome(EventOutcome(EventOutcomeType.COMPLETED, at(4)))

        skipped = make_event("evt_skip")
        advance(skipped, EventStatus.SCHEDULED, EventStatus.SKIPPED)
        with pytest.raises(DomainValidationError):
            skipped.record_outcome(EventOutcome(EventOutcomeType.ABANDONED, at(4)))


class TestReflectionLink:
    def test_reflection_requires_completed_event(self, make_event):
        event = make_event()
        with pytest.raises(DomainValidationError):
            event.link_reflection(ReflectionId("ref_001"))

    def test_reflection_linked_once_after_completion(self, make_event):
        event = make_event()
        advance(
            event,
            EventStatus.SCHEDULED,
            EventStatus.READY,
            EventStatus.STARTED,
            EventStatus.COMPLETED,
        )
        event.link_reflection(ReflectionId("ref_001"))
        assert event.reflection_id == ReflectionId("ref_001")
        with pytest.raises(ImmutabilityViolationError):
            event.link_reflection(ReflectionId("ref_002"))
