"""Event Disturber lifecycle and the mandatory causal chain
(STATE_MACHINES.md section 5; DOMAIN_MODEL.md Principle 24)."""

import dataclasses

import pytest

from paios.domain.entities.event_disturber import EventDisturber
from paios.domain.enums import (
    DisturberResolutionStatus,
    DisturberSeverity,
    DisturberState,
    DisturberType,
)
from paios.domain.errors import InvalidTransitionError
from paios.domain.value_objects.identifiers import (
    ContextWindowId,
    EventDisturberId,
    EventId,
    UserId,
)

from tests.domain.conftest import T0, at


@pytest.fixture
def disturber() -> EventDisturber:
    return EventDisturber(
        event_disturber_id=EventDisturberId("dist_001"),
        user_id=UserId("user_001"),
        type=DisturberType.WORK,
        description="Team Lead requested overtime for production issue",
        severity=DisturberSeverity.HIGH,
        occurred_at=T0,
        affected_scheduled_event_ids=(EventId("evt_003"), EventId("evt_004")),
    )


class TestDisturberLifecycle:
    def test_full_chain(self, disturber):
        disturber.record(at(1))
        disturber.analyze(at(2))
        disturber.apply(at(3), ContextWindowId("win_002"))
        disturber.resolve(at(10))
        disturber.archive(at(60))
        assert disturber.state is DisturberState.ARCHIVED
        assert disturber.resolution_status is DisturberResolutionStatus.RESOLVED

    def test_apply_records_context_window_not_event(self, disturber):
        disturber.record(at(1))
        disturber.analyze(at(2))
        disturber.apply(at(3), ContextWindowId("win_002"))
        assert disturber.resulting_context_window_id == ContextWindowId("win_002")

    def test_resolve_actor_is_scheduler(self, disturber):
        disturber.record(at(1))
        disturber.analyze(at(2))
        disturber.apply(at(3), ContextWindowId("win_002"))
        record = disturber.resolve(at(10))
        assert record.actor == "Scheduler"

    def test_structural_invariant_no_event_reference_field(self, disturber):
        field_names = {field.name for field in dataclasses.fields(disturber)}
        assert "event_id" not in field_names
        assert "resulting_context_window_id" in field_names


class TestInvalidDisturberTransitions:
    """Invalid: Detected -> Applied; Archived -> Analyzed (STATE_MACHINES.md)."""

    def test_detected_cannot_skip_to_applied(self, disturber):
        with pytest.raises(InvalidTransitionError):
            disturber.apply(at(1), ContextWindowId("win_002"))

    def test_archived_cannot_reanalyze(self, disturber):
        disturber.record(at(1))
        disturber.analyze(at(2))
        disturber.apply(at(3), ContextWindowId("win_002"))
        disturber.resolve(at(4))
        disturber.archive(at(5))
        with pytest.raises(InvalidTransitionError):
            disturber.analyze(at(6))

    def test_transition_history_cannot_be_replaced(self, disturber):
        from paios.domain.errors import ImmutabilityViolationError
        from paios.domain.state_machines.definitions import DISTURBER_STATE_MACHINE
        from paios.domain.state_machines.machine import TransitionHistory

        with pytest.raises(ImmutabilityViolationError):
            disturber._history = TransitionHistory(
                DISTURBER_STATE_MACHINE, DisturberState.DETECTED
            )
