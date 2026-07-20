"""Context Window lifecycle (STATE_MACHINES.md section 3)."""

import pytest

from paios.domain.enums import ContextWindowState
from paios.domain.errors import ImmutabilityViolationError, InvalidTransitionError
from paios.domain.state_machines.definitions import CONTEXT_WINDOW_STATE_MACHINE
from paios.domain.state_machines.machine import TransitionHistory
from paios.domain.value_objects.time import Duration

from tests.domain.conftest import T0, at


class TestContextWindowLifecycle:
    def test_starts_created(self, make_window):
        window = make_window()
        assert window.current_state is ContextWindowState.CREATED
        assert not window.is_active

    def test_activation_records_start(self, make_window):
        window = make_window()
        window.activate(T0, reason_started="Arrived at office")
        assert window.is_active
        assert window.start_time == T0
        assert window.reason_started == "Arrived at office"

    def test_active_to_changing_to_expired(self, make_window):
        window = make_window()
        window.activate(T0)
        window.mark_changing(at(60), reason="Team Lead requested overtime")
        assert window.current_state is ContextWindowState.CHANGING
        window.expire(at(65), reason_ended="Replacement window active")
        assert window.current_state is ContextWindowState.EXPIRED
        assert window.reason_ended == "Replacement window active"

    def test_expire_computes_duration(self, make_window):
        window = make_window()
        window.activate(T0)
        window.expire(at(465))
        assert window.end_time == at(465)
        assert window.duration == Duration(465)

    def test_full_path_to_archived(self, make_window):
        window = make_window()
        window.activate(T0)
        window.expire(at(120))
        window.archive(at(200))
        assert window.current_state is ContextWindowState.ARCHIVED

    def test_transition_evidence_is_recorded(self, make_window):
        window = make_window()
        window.activate(T0)
        window.expire(at(120))
        assert [record.to_state for record in window.transitions] == [
            ContextWindowState.ACTIVE,
            ContextWindowState.EXPIRED,
        ]
        assert window.transitions[0].actor == "Runtime"


class TestInvalidContextWindowTransitions:
    """Invalid: Created -> Expired, Expired -> Active, Archived -> Active."""

    def test_created_cannot_expire(self, make_window):
        with pytest.raises(InvalidTransitionError):
            make_window().expire(T0)

    def test_expired_cannot_reactivate(self, make_window):
        window = make_window()
        window.activate(T0)
        window.expire(at(60))
        with pytest.raises(InvalidTransitionError):
            window.activate(at(61))

    def test_archived_cannot_reactivate(self, make_window):
        window = make_window()
        window.activate(T0)
        window.expire(at(60))
        window.archive(at(90))
        with pytest.raises(InvalidTransitionError):
            window.activate(at(91))


class TestContextWindowImmutability:
    """Past Context Windows are immutable (RUNTIME_EXECUTION.md - Core
    Guarantees; STATE_MACHINES.md section 3)."""

    def test_expired_window_facts_are_frozen(self, make_window):
        window = make_window()
        window.activate(T0)
        window.expire(at(60))
        with pytest.raises(ImmutabilityViolationError):
            window.start_time = at(999)
        with pytest.raises(ImmutabilityViolationError):
            window.reason_ended = "rewritten history"

    def test_archived_window_facts_are_frozen(self, make_window):
        window = make_window()
        window.activate(T0)
        window.expire(at(60))
        window.archive(at(90))
        with pytest.raises(ImmutabilityViolationError):
            window.duration = Duration(1)

    def test_failed_expire_does_not_mutate_facts(self, make_window):
        window = make_window()
        with pytest.raises(InvalidTransitionError):
            window.expire(T0)
        assert window.end_time is None
        assert window.duration is None

    def test_transition_history_cannot_be_replaced(self, make_window):
        window = make_window()
        window.activate(T0)
        with pytest.raises(ImmutabilityViolationError):
            window._history = TransitionHistory(
                CONTEXT_WINDOW_STATE_MACHINE, ContextWindowState.CREATED
            )
