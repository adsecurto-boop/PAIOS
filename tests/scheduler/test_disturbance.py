"""The mandatory disturbance chain (DOMAIN_MODEL.md Principle 24) and
Overtaken semantics."""

from paios.domain.enums import (
    ContextWindowState,
    DisturberResolutionStatus,
    DisturberState,
    EventStatus,
)
from paios.domain.value_objects.identifiers import (
    EventDisturberId,
    EventId,
    RecommendationId,
)
from paios.runtime.runtime_state import IdleExecutionContext

from tests.scheduler.conftest import (
    at,
    build_applied_disturber,
    build_pending_recommendation,
    publish_disturbance,
    publish_time,
    seed_context,
    seed_running_event,
)


def seed_disturbed(factory):
    seed_context(factory)
    seed_running_event(factory)
    factory.event_disturbers().save(build_applied_disturber())


class TestDisturbanceChain:
    def test_disturbance_interrupts_via_the_mandatory_chain(self, system):
        wired = system(seed=seed_disturbed)
        state = wired.kernel.runtime_state
        running = state.events[0]
        assert running.status is EventStatus.STARTED
        publish_disturbance(wired.kernel, at(30), "dist_001")
        # 1. Context Window transition first
        window = state.context_windows[0]
        assert window.current_state is ContextWindowState.EXPIRED
        assert window.reason_ended == "Disturbance"
        # 2. then Event State Transition, never directly from the Disturber
        assert running.status is EventStatus.INTERRUPTED
        assert running.transitions[-1].actor == "Scheduler"
        # 3. execution context returns to idle
        assert isinstance(
            state.execution_context, IdleExecutionContext
        )
        # 4. Scheduler resolves the Applied disturber (STATE_MACHINES §5)
        disturber = state.event_disturbers[0]
        assert disturber.state is DisturberState.RESOLVED
        assert disturber.resolution_status is DisturberResolutionStatus.RESOLVED
        stored = wired.factory.event_disturbers().get(
            EventDisturberId("dist_001")
        )
        assert stored.state is DisturberState.RESOLVED

    def test_interrupted_event_can_resume(self, system):
        wired = system(seed=seed_disturbed)
        running = wired.kernel.runtime_state.events[0]
        publish_disturbance(wired.kernel, at(30), "dist_001")
        wired.scheduler.user_resumed(running.event_id, at(60))
        assert running.status is EventStatus.RESUMED
        assert running.is_running

    def test_interrupted_event_can_be_cancelled(self, system):
        wired = system(seed=seed_disturbed)
        running = wired.kernel.runtime_state.events[0]
        publish_disturbance(wired.kernel, at(30), "dist_001")
        wired.scheduler.user_cancelled(running.event_id, at(60))
        assert running.status is EventStatus.CANCELLED


class TestOvertaken:
    def test_interrupted_event_overtaken_by_higher_priority(self, system):
        def seed(factory):
            seed_disturbed(factory)
            factory.recommendations().save(
                build_pending_recommendation("rec_hi", priority=10.0)
            )

        wired = system(seed=seed)
        interrupted = wired.kernel.runtime_state.events[0]
        publish_disturbance(wired.kernel, at(30), "dist_001")
        assert interrupted.status is EventStatus.INTERRUPTED
        wired.scheduler.accept_recommendation(RecommendationId("rec_hi"), at(31))
        publish_time(wired.kernel, at(32))
        assert interrupted.status is EventStatus.OVERTAKEN
        assert (
            wired.factory.events().get(EventId("evt_run")).status
            is EventStatus.OVERTAKEN
        )
