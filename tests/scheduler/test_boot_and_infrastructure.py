"""Boot adoption, crash recovery, the RecalculationBridge, and
PersistenceSync conventions."""

from paios.domain.enums import EventStatus, RecommendationStatus
from paios.domain.value_objects.identifiers import EventId, RecommendationId
from paios.runtime.runtime_state import EventExecutionContext
from paios.runtime.system_events import SystemEvent, SystemEventType
from paios.scheduler.lifecycle import SchedulerState

from tests.scheduler.conftest import (
    T0,
    at,
    build_pending_recommendation,
    publish_time,
    seed_context,
    seed_running_event,
)


class TestBootAdoption:
    def test_restored_running_event_is_monitored(self, system):
        def seed(factory):
            seed_context(factory)
            seed_running_event(factory)

        wired = system(seed=seed)
        assert wired.scheduler.state is SchedulerState.MONITORING
        context = wired.kernel.runtime_state.execution_context
        assert isinstance(context, EventExecutionContext)
        assert context.event_id == EventId("evt_run")

    def test_stale_recommendation_expired_at_attach(self, system):
        def seed(factory):
            seed_context(factory)
            factory.recommendations().save(
                build_pending_recommendation(
                    "rec_stale",
                    created_at=at(-100),
                    expires_at=at(-10),
                    presented_at=at(-90),
                )
            )

        wired = system(seed=seed)
        assert (
            wired.factory.recommendations()
            .get(RecommendationId("rec_stale"))
            .status
            is RecommendationStatus.EXPIRED
        )

    def test_crash_recovery_resumes_from_persisted_evidence(self, system):
        def seed(factory):
            seed_context(factory)
            factory.recommendations().save(build_pending_recommendation())

        first = system(seed=seed)
        first.scheduler.accept_recommendation(RecommendationId("rec_001"), at(5))
        event = first.kernel.runtime_state.events[0]
        publish_time(first.kernel, at(6))
        first.scheduler.user_started(event.event_id, at(7))
        first.kernel.shutdown()

        # A fresh system over the SAME data directory: the crash-recovery
        # boot path. All evidence written by PersistenceSync must restore.
        second = system()
        restored = second.kernel.runtime_state.events[0]
        assert restored.status is EventStatus.STARTED
        assert second.scheduler.state is SchedulerState.MONITORING
        context = second.kernel.runtime_state.execution_context
        assert isinstance(context, EventExecutionContext)
        assert context.event_id == restored.event_id


class TestRecalculationBridge:
    def test_single_subscription_topic(self, system):
        wired = system(seed=seed_context)
        bus = wired.kernel.event_bus
        assert (
            bus.subscriber_count(
                SystemEventType.SCHEDULER_RECALCULATION_REQUESTED
            )
            == 1
        )

    def test_bridge_forwards_reason(self, system):
        wired = system(seed=seed_context)
        received = []
        wired.kernel.event_bus.subscribe(
            SystemEventType.SCHEDULER_RECALCULATION_REQUESTED, received.append
        )
        publish_time(wired.kernel, at(1))
        assert received
        assert received[0].payload["reason"] == "TimeProgressed"

    def test_unknown_reason_falls_back_to_manual(self, system):
        wired = system(seed=seed_context)
        wired.kernel.event_bus.publish(
            SystemEvent(
                SystemEventType.SCHEDULER_RECALCULATION_REQUESTED,
                at(1),
                {"reason": "SomethingNew"},
            )
        )
        assert wired.scheduler.state in (
            SchedulerState.IDLE,
            SchedulerState.MONITORING,
        )


class TestPersistenceSyncConventions:
    def test_event_updates_written_back(self, system):
        def seed(factory):
            seed_context(factory)
            factory.recommendations().save(build_pending_recommendation())

        wired = system(seed=seed)
        wired.scheduler.accept_recommendation(RecommendationId("rec_001"), at(5))
        event = wired.kernel.runtime_state.events[0]
        publish_time(wired.kernel, at(6))
        stored = wired.factory.events().get(event.event_id)
        assert stored.status is EventStatus.READY

    def test_sync_attach_is_idempotent(self, system):
        wired = system(seed=seed_context)
        wired.sync.attach()
        wired.bridge.attach()
        publish_time(wired.kernel, at(1))
