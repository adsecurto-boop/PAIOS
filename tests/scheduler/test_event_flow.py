"""Event flow end-to-end: ready, start, pause, resume, complete, skip,
cancel, archive — with ExecutionContext and Context Window effects."""

from paios.domain.enums import (
    ContextWindowState,
    EventOutcomeType,
    EventStatus,
)
from paios.domain.value_objects.event_outcome import EventOutcome
from paios.domain.value_objects.identifiers import RecommendationId
from paios.runtime.runtime_state import (
    EventExecutionContext,
    IdleExecutionContext,
    IdleReason,
)

from tests.scheduler.conftest import (
    at,
    build_pending_recommendation,
    publish_time,
    seed_context,
)

REC = RecommendationId("rec_001")


def seed(factory):
    seed_context(factory)
    factory.recommendations().save(build_pending_recommendation())


def accept_and_materialize(wired):
    wired.scheduler.accept_recommendation(REC, at(5))
    return wired.kernel.runtime_state.events[0]


class TestReadyAndStart:
    def test_future_slot_becomes_ready_when_time_arrives(self, system):
        def seed_future(factory):
            seed_context(factory)
            factory.recommendations().save(
                build_pending_recommendation(suggested_timing=at(60))
            )

        wired = system(seed=seed_future)
        event = accept_and_materialize(wired)
        assert event.status is EventStatus.SCHEDULED
        publish_time(wired.kernel, at(30))
        assert event.status is EventStatus.SCHEDULED
        publish_time(wired.kernel, at(61))
        assert event.status is EventStatus.READY

    def test_user_start_activates_window_and_execution_context(self, system):
        wired = system(seed=seed)
        event = accept_and_materialize(wired)
        publish_time(wired.kernel, at(6))
        wired.scheduler.user_started(event.event_id, at(7))
        assert event.status is EventStatus.STARTED
        context = wired.kernel.runtime_state.execution_context
        assert isinstance(context, EventExecutionContext)
        assert context.event_id == event.event_id
        window = wired.kernel.runtime_state.context_windows[0]
        assert window.current_state is ContextWindowState.ACTIVE


class TestPauseResumeComplete:
    def start_event(self, wired):
        event = accept_and_materialize(wired)
        publish_time(wired.kernel, at(6))
        wired.scheduler.user_started(event.event_id, at(7))
        return event

    def test_pause_swaps_to_idle(self, system):
        wired = system(seed=seed)
        event = self.start_event(wired)
        wired.scheduler.user_paused(event.event_id, at(20))
        assert event.status is EventStatus.PAUSED
        context = wired.kernel.runtime_state.execution_context
        assert isinstance(context, IdleExecutionContext)

    def test_resume_restores_event_context(self, system):
        wired = system(seed=seed)
        event = self.start_event(wired)
        wired.scheduler.user_paused(event.event_id, at(20))
        wired.scheduler.user_resumed(event.event_id, at(30))
        assert event.status is EventStatus.RESUMED
        assert event.is_running
        context = wired.kernel.runtime_state.execution_context
        assert isinstance(context, EventExecutionContext)

    def test_complete_records_evidence_and_expires_window(self, system):
        wired = system(seed=seed)
        event = self.start_event(wired)
        wired.scheduler.user_completed(
            event.event_id,
            at(67),
            outcome=EventOutcome(EventOutcomeType.COMPLETED, at(67)),
            actual_outcome="Chapter finished",
        )
        assert event.status is EventStatus.COMPLETED
        assert event.outcome.outcome_type is EventOutcomeType.COMPLETED
        assert event.actual_outcome == "Chapter finished"
        assert event.end_time == at(67)
        window = wired.kernel.runtime_state.context_windows[0]
        assert window.current_state is ContextWindowState.EXPIRED
        context = wired.kernel.runtime_state.execution_context
        assert isinstance(context, IdleExecutionContext)
        assert context.reason is IdleReason.BETWEEN_EVENTS
        stored = wired.factory.events().get(event.event_id)
        assert stored.status is EventStatus.COMPLETED
        assert stored.outcome.outcome_type is EventOutcomeType.COMPLETED

    def test_resumed_event_completes_via_documented_edges(self, system):
        wired = system(seed=seed)
        event = self.start_event(wired)
        wired.scheduler.user_paused(event.event_id, at(20))
        wired.scheduler.user_resumed(event.event_id, at(30))
        wired.scheduler.user_completed(event.event_id, at(60))
        assert event.status is EventStatus.COMPLETED


class TestSkipCancelArchive:
    def test_unstarted_scheduled_event_is_skipped_after_slot_passes(
        self, system
    ):
        def seed_future(factory):
            seed_context(factory)
            factory.recommendations().save(
                build_pending_recommendation(suggested_timing=at(60))
            )

        wired = system(seed=seed_future)
        event = accept_and_materialize(wired)
        assert event.status is EventStatus.SCHEDULED
        publish_time(wired.kernel, at(300))
        assert event.status is EventStatus.SKIPPED
        assert (
            wired.factory.events().get(event.event_id).status
            is EventStatus.SKIPPED
        )

    def test_cancel_scheduled_event(self, system):
        def seed_future(factory):
            seed_context(factory)
            factory.recommendations().save(
                build_pending_recommendation(suggested_timing=at(60))
            )

        wired = system(seed=seed_future)
        event = accept_and_materialize(wired)
        assert event.status is EventStatus.SCHEDULED
        wired.scheduler.user_cancelled(event.event_id, at(10), reason="No time")
        assert event.status is EventStatus.CANCELLED
        assert wired.scheduler.plan.entry_for(event.event_id) is None

    def test_ready_event_skipped_after_slot_passes(self, system):
        """ADR-003: a Ready Event whose opportunity passes is Skipped."""
        wired = system(seed=seed)
        event = accept_and_materialize(wired)
        assert event.status is EventStatus.READY  # immediately due slot
        publish_time(wired.kernel, at(300))
        assert event.status is EventStatus.SKIPPED
        assert (
            wired.factory.events().get(event.event_id).status
            is EventStatus.SKIPPED
        )

    def test_ready_event_can_be_cancelled(self, system):
        """ADR-003: readiness never removes the user's freedom not to start."""
        wired = system(seed=seed)
        event = accept_and_materialize(wired)
        assert event.status is EventStatus.READY
        wired.scheduler.user_cancelled(
            event.event_id, at(10), reason="Changed my mind"
        )
        assert event.status is EventStatus.CANCELLED
        assert (
            wired.factory.events().get(event.event_id).status
            is EventStatus.CANCELLED
        )

    def test_archive_completed_event(self, system):
        wired = system(seed=seed)
        event = accept_and_materialize(wired)
        publish_time(wired.kernel, at(6))
        wired.scheduler.user_started(event.event_id, at(7))
        wired.scheduler.user_completed(event.event_id, at(60))
        wired.scheduler.archive_event(event.event_id, at(600))
        assert event.status is EventStatus.ARCHIVED
        assert (
            wired.factory.events().get(event.event_id).status
            is EventStatus.ARCHIVED
        )


class TestSingleRunningEventRule:
    def test_starting_second_event_pauses_the_first(self, system):
        def seed_two(factory):
            seed_context(factory)
            factory.recommendations().save(
                build_pending_recommendation("rec_001", priority=5.0)
            )
            factory.recommendations().save(
                build_pending_recommendation("rec_002", priority=1.0)
            )

        wired = system(seed=seed_two)
        wired.scheduler.accept_recommendation(RecommendationId("rec_001"), at(5))
        wired.scheduler.accept_recommendation(RecommendationId("rec_002"), at(5))
        state = wired.kernel.runtime_state
        first, second = state.events
        publish_time(wired.kernel, at(6))
        wired.scheduler.user_started(first.event_id, at(7))
        wired.scheduler.user_started(second.event_id, at(10))
        assert first.status is EventStatus.PAUSED
        assert second.status is EventStatus.STARTED
        running = [event for event in state.events if event.is_running]
        assert running == [second]
