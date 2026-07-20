"""Generic state-machine machinery and immutable transition history."""

from dataclasses import FrozenInstanceError

import pytest

from paios.domain.enums import EventStatus
from paios.domain.errors import InvalidTransitionError
from paios.domain.state_machines.definitions import EVENT_STATE_MACHINE
from paios.domain.state_machines.machine import StateMachine, TransitionHistory

from tests.domain.conftest import T0, at


class TestStateMachine:
    def test_allowed_transition(self):
        assert EVENT_STATE_MACHINE.can_transition(
            EventStatus.RECOMMENDED, EventStatus.SCHEDULED
        )

    def test_disallowed_transition(self):
        assert not EVENT_STATE_MACHINE.can_transition(
            EventStatus.RECOMMENDED, EventStatus.STARTED
        )

    def test_validate_raises_with_context(self):
        with pytest.raises(InvalidTransitionError, match="Event Lifecycle"):
            EVENT_STATE_MACHINE.validate(
                EventStatus.SCHEDULED, EventStatus.COMPLETED
            )

    def test_terminal_states(self):
        assert EVENT_STATE_MACHINE.is_terminal(EventStatus.ARCHIVED)
        assert EVENT_STATE_MACHINE.is_terminal(EventStatus.OVERTAKEN)
        assert not EVENT_STATE_MACHINE.is_terminal(EventStatus.COMPLETED)


class TestTransitionHistory:
    def make_history(self) -> TransitionHistory[EventStatus]:
        return TransitionHistory(EVENT_STATE_MACHINE, EventStatus.RECOMMENDED)

    def test_starts_at_initial_state_with_no_records(self):
        history = self.make_history()
        assert history.current_state is EventStatus.RECOMMENDED
        assert history.records == ()

    def test_apply_appends_and_advances(self):
        history = self.make_history()
        record = history.apply(EventStatus.SCHEDULED, T0, "Scheduler", "accepted")
        assert history.current_state is EventStatus.SCHEDULED
        assert history.records == (record,)
        assert record.from_state is EventStatus.RECOMMENDED
        assert record.to_state is EventStatus.SCHEDULED
        assert record.actor == "Scheduler"
        assert record.reason == "accepted"

    def test_invalid_transition_leaves_history_untouched(self):
        history = self.make_history()
        with pytest.raises(InvalidTransitionError):
            history.apply(EventStatus.COMPLETED, T0, "Scheduler")
        assert history.current_state is EventStatus.RECOMMENDED
        assert history.records == ()

    def test_records_are_immutable(self):
        history = self.make_history()
        record = history.apply(EventStatus.SCHEDULED, T0, "Scheduler")
        with pytest.raises(FrozenInstanceError):
            record.to_state = EventStatus.COMPLETED

    def test_records_view_cannot_mutate_internal_history(self):
        history = self.make_history()
        history.apply(EventStatus.SCHEDULED, T0, "Scheduler")
        view = history.records
        assert isinstance(view, tuple)
        history.apply(EventStatus.READY, at(5), "Scheduler")
        assert len(view) == 1
        assert len(history.records) == 2
