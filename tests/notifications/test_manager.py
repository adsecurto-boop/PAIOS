"""Routing: every supported event maps to its notification; the observer
contract (never disturb the publisher) holds under all failures."""

from datetime import timedelta

from paios.notifications import (
    Category,
    NotificationConfig,
    NotificationManager,
    Severity,
)
from paios.runtime.system_events import SystemEventType

from tests.notifications.conftest import (
    NOON,
    RecordingProvider,
    disturber_entity,
    event,
    event_entity,
    recommendation_entity,
)


def make_manager(bus, **config):
    provider = RecordingProvider()
    manager = NotificationManager(
        NotificationConfig(**config), providers=(provider,)
    )
    manager.attach(bus)
    return manager, provider


class TestRouting:
    def test_recommendation_generated(self, bus):
        manager, provider = make_manager(bus)
        bus.publish(
            event(
                SystemEventType.RECOMMENDATION_GENERATED,
                {"recommendation": recommendation_entity()},
            )
        )
        assert [n.message for n in provider.sent] == [
            "Study ISTQB for 60 minutes"
        ]
        assert provider.sent[0].category is Category.RECOMMENDATION

    def test_recommendation_accepted_and_rejected(self, bus):
        manager, provider = make_manager(bus)
        bus.publish(
            event(
                SystemEventType.PLAN_UPDATED,
                {
                    "recommendations_updated": (
                        recommendation_entity(status="Accepted"),
                        recommendation_entity(
                            reason="rest", status="Rejected"
                        ),
                        recommendation_entity(
                            reason="churn", status="Consumed"
                        ),
                    )
                },
            )
        )
        assert [n.message for n in provider.sent] == [
            "Recommendation accepted: Study ISTQB for 60 minutes",
            "Recommendation rejected: rest",
        ]

    def test_event_lifecycle_states(self, bus):
        manager, provider = make_manager(bus, cooldown_seconds=0)
        expectations = {
            "Ready": "Time to start Deep work",
            "Started": "Started: Deep work",
            "Paused": "Paused: Deep work",
            "Resumed": "Resumed: Deep work",
            "Completed": "Deep work completed",
            "Cancelled": "Cancelled: Deep work",
        }
        for status, message in expectations.items():
            bus.publish(
                event(
                    SystemEventType.EVENT_STATE_CHANGED,
                    {"event": event_entity(status=status)},
                )
            )
        assert [n.message for n in provider.sent] == list(
            expectations.values()
        )

    def test_bookkeeping_event_states_are_silent(self, bus):
        manager, provider = make_manager(bus)
        for status in ("Recommended", "Scheduled", "Archived"):
            bus.publish(
                event(
                    SystemEventType.EVENT_STATE_CHANGED,
                    {"event": event_entity(status=status)},
                )
            )
        assert provider.sent == []

    def test_context_time_learning_and_lifecycle(self, bus):
        manager, provider = make_manager(bus)
        for event_type, expected in (
            (SystemEventType.RUNNING_CONTEXT_CHANGED, "Context changed"),
            (SystemEventType.TIME_PROGRESSED, "Time progressed"),
            (SystemEventType.INSIGHT_GENERATED, "New insight generated"),
            (SystemEventType.REFLECTION_CREATED, "Reflection recorded"),
            (SystemEventType.HABIT_DETECTED, "New habit detected"),
            (SystemEventType.KERNEL_BOOTED, "Application started"),
            (SystemEventType.KERNEL_SHUTDOWN, "Application stopped"),
        ):
            bus.publish(event(event_type))
            assert expected in provider.sent[-1].message

    def test_disturbance_severity_mapping(self, bus):
        manager, provider = make_manager(bus, cooldown_seconds=0)
        bus.publish(
            event(
                SystemEventType.DISTURBANCE_DETECTED,
                {"event_disturber": disturber_entity(severity="High")},
            )
        )
        bus.publish(
            event(
                SystemEventType.DISTURBANCE_DETECTED,
                {
                    "event_disturber": disturber_entity(
                        description="Doorbell", severity="Low"
                    )
                },
            )
        )
        assert provider.sent[0].severity is Severity.CRITICAL
        assert "Unexpected interruption recorded" in provider.sent[0].message
        assert provider.sent[1].severity is Severity.NORMAL

    def test_attach_announces_application_started(self, bus):
        provider = RecordingProvider()
        manager = NotificationManager(providers=(provider,))
        manager.attach(bus, started_at=NOON)
        assert [n.message for n in provider.sent] == ["Application started"]


class TestObserverContract:
    def test_malformed_payload_never_raises(self, bus):
        manager, provider = make_manager(bus)
        bus.publish(
            event(
                SystemEventType.RECOMMENDATION_GENERATED,
                {"recommendation": object()},  # no .reason attribute
            )
        )  # must not raise into the publisher
        assert provider.sent == []

    def test_failing_provider_is_isolated(self, bus):
        healthy = RecordingProvider()
        manager = NotificationManager(
            providers=(RecordingProvider(fail=True), healthy)
        )
        manager.attach(bus)
        bus.publish(event(SystemEventType.TIME_PROGRESSED))
        assert [n.message for n in healthy.sent] == ["Time progressed"]
        assert manager.delivered == 1

    def test_detach_stops_observing(self, bus):
        manager, provider = make_manager(bus)
        manager.detach()
        bus.publish(event(SystemEventType.TIME_PROGRESSED))
        assert provider.sent == []
        assert manager.attached is False

    def test_attach_is_idempotent_per_bus(self, bus):
        manager, provider = make_manager(bus)
        manager.attach(bus)  # second attach: no duplicate subscriptions
        bus.publish(event(SystemEventType.TIME_PROGRESSED))
        assert len(provider.sent) == 1

    def test_manager_never_publishes(self, bus):
        published = []
        original = bus.publish
        bus.publish = lambda e: (published.append(e), original(e))
        manager, provider = make_manager(bus)
        original(event(SystemEventType.TIME_PROGRESSED))
        assert published == []  # the observer only listens


class TestDeduplication:
    def test_identical_within_cooldown_dropped(self, bus):
        manager, provider = make_manager(bus, cooldown_seconds=300)
        bus.publish(event(SystemEventType.TIME_PROGRESSED, at=NOON))
        bus.publish(
            event(
                SystemEventType.TIME_PROGRESSED,
                at=NOON + timedelta(seconds=299),
            )
        )
        assert len(provider.sent) == 1
        assert manager.deduplicated == 1
        assert len(manager.history) == 1  # duplicates never reach history

    def test_identical_after_cooldown_delivered(self, bus):
        manager, provider = make_manager(bus, cooldown_seconds=300)
        bus.publish(event(SystemEventType.TIME_PROGRESSED, at=NOON))
        bus.publish(
            event(
                SystemEventType.TIME_PROGRESSED,
                at=NOON + timedelta(seconds=300),
            )
        )
        assert len(provider.sent) == 2

    def test_different_messages_are_not_duplicates(self, bus):
        manager, provider = make_manager(bus, cooldown_seconds=300)
        for reason in ("Study ISTQB", "Rest now"):
            bus.publish(
                event(
                    SystemEventType.RECOMMENDATION_GENERATED,
                    {"recommendation": recommendation_entity(reason=reason)},
                )
            )
        assert len(provider.sent) == 2
