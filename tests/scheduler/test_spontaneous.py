"""Spontaneous user actions (ruling G4): reality enters through the front
door of the lifecycle."""

import pytest

from paios.domain.enums import ContextWindowState, EventStatus
from paios.domain.value_objects.identifiers import UserId
from paios.runtime.runtime_state import EventExecutionContext
from paios.scheduler.exceptions import UnknownWorkError

from tests.scheduler.conftest import (
    at,
    seed_context,
    seed_running_event,
)

USER = UserId("user_001")


class TestSpontaneousActions:
    def test_spontaneous_action_becomes_running_event(self, system):
        wired = system(seed=seed_context)
        event = wired.scheduler.report_spontaneous_action(
            USER, "health", "Went for an unplanned run", at(10)
        )
        assert event.status is EventStatus.STARTED
        assert event.start_time == at(10)
        assert [record.to_state for record in event.transitions] == [
            EventStatus.SCHEDULED,
            EventStatus.READY,
            EventStatus.STARTED,
        ]
        assert all(
            record.reason == "Spontaneous user action"
            for record in event.transitions
        )
        context = wired.kernel.runtime_state.execution_context
        assert isinstance(context, EventExecutionContext)
        assert context.event_id == event.event_id
        window = wired.kernel.runtime_state.context_windows[0]
        assert window.current_state is ContextWindowState.ACTIVE

    def test_spontaneous_action_is_persisted(self, system):
        wired = system(seed=seed_context)
        event = wired.scheduler.report_spontaneous_action(
            USER, "health", "Went for an unplanned run", at(10)
        )
        stored = wired.factory.events().get(event.event_id)
        assert stored.status is EventStatus.STARTED
        assert len(wired.factory.context_windows().list()) == 1

    def test_spontaneous_action_pauses_running_event(self, system):
        def seed(factory):
            seed_context(factory)
            seed_running_event(factory)

        wired = system(seed=seed)
        planned = wired.kernel.runtime_state.events[0]
        assert planned.status is EventStatus.STARTED
        spontaneous = wired.scheduler.report_spontaneous_action(
            USER, "social", "Friend arrived", at(20)
        )
        assert planned.status is EventStatus.PAUSED
        assert spontaneous.status is EventStatus.STARTED
        # The planned Event's window was auto-closed by the new activation.
        planned_window = next(
            window
            for window in wired.kernel.runtime_state.context_windows
            if window.window_id == planned.context_window_id
        )
        assert planned_window.current_state is ContextWindowState.EXPIRED

    def test_spontaneous_action_requires_a_context(self, system):
        wired = system()  # no Context seeded
        with pytest.raises(UnknownWorkError):
            wired.scheduler.report_spontaneous_action(
                USER, "health", "Unplanned run", at(10)
            )
