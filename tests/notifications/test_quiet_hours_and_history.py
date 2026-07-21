"""Quiet hours, history/unread behaviour, provider abstraction."""

from datetime import time

import pytest

from paios.notifications import (
    ConsoleProvider,
    NotificationConfig,
    NotificationManager,
    NotificationProvider,
    NullProvider,
    ProviderError,
    QuietHours,
)
from paios.notifications.history import NotificationHistory
from paios.notifications.notification import Category, Notification, Severity
from paios.runtime.system_events import SystemEventType

from tests.notifications.conftest import (
    NIGHT,
    NOON,
    RecordingProvider,
    disturber_entity,
    event,
)

MISSION_WINDOW = QuietHours(time(22, 0), time(7, 0))


def quiet_manager(bus, provider):
    manager = NotificationManager(
        NotificationConfig(quiet_hours=MISSION_WINDOW, cooldown_seconds=0),
        providers=(provider,),
    )
    manager.attach(bus)
    return manager


class TestQuietHours:
    def test_window_crossing_midnight(self):
        window = MISSION_WINDOW
        assert window.contains(time(23, 30)) is True
        assert window.contains(time(22, 0)) is True
        assert window.contains(time(3, 0)) is True
        assert window.contains(time(6, 59)) is True
        assert window.contains(time(7, 0)) is False
        assert window.contains(time(12, 0)) is False

    def test_same_day_window(self):
        window = QuietHours(time(12, 0), time(14, 0))
        assert window.contains(time(13, 0)) is True
        assert window.contains(time(15, 0)) is False

    def test_parse(self):
        assert QuietHours.parse("22:00-07:00") == MISSION_WINDOW
        with pytest.raises(ValueError):
            QuietHours.parse("bedtime")

    def test_normal_held_during_quiet_hours(self, bus):
        provider = RecordingProvider()
        manager = quiet_manager(bus, provider)
        bus.publish(event(SystemEventType.TIME_PROGRESSED, at=NIGHT))
        assert provider.sent == []  # not routed...
        assert manager.held_quiet == 1
        assert manager.history.unread_count == 1  # ...but waiting, unread

    def test_critical_bypasses_quiet_hours(self, bus):
        provider = RecordingProvider()
        manager = quiet_manager(bus, provider)
        bus.publish(
            event(
                SystemEventType.DISTURBANCE_DETECTED,
                {"event_disturber": disturber_entity(severity="High")},
                at=NIGHT,
            )
        )
        assert len(provider.sent) == 1
        assert provider.sent[0].severity is Severity.CRITICAL

    def test_daytime_routes_normally(self, bus):
        provider = RecordingProvider()
        manager = quiet_manager(bus, provider)
        bus.publish(event(SystemEventType.TIME_PROGRESSED, at=NOON))
        assert len(provider.sent) == 1
        assert manager.held_quiet == 0


def make_notification(message="hello", read=False):
    return Notification(
        category=Category.SYSTEM,
        title="t",
        message=message,
        severity=Severity.NORMAL,
        occurred_at=NOON,
        read=read,
    )


class TestHistory:
    def test_unread_count_and_mark_all_read(self):
        history = NotificationHistory()
        for index in range(3):
            history.record(make_notification(f"m{index}"))
        assert history.unread_count == 3
        assert [n.message for n in history.unread()] == ["m2", "m1", "m0"]
        assert history.mark_all_read() == 3
        assert history.unread_count == 0
        assert history.unread() == []

    def test_entries_newest_first(self):
        history = NotificationHistory()
        history.record(make_notification("first"))
        history.record(make_notification("second"))
        assert [n.message for n in history.entries()] == ["second", "first"]

    def test_clear(self):
        history = NotificationHistory()
        history.record(make_notification())
        assert history.clear() == 1
        assert len(history) == 0
        assert history.clear() == 0

    def test_ring_limit_drops_oldest(self):
        history = NotificationHistory(limit=2)
        for index in range(3):
            history.record(make_notification(f"m{index}"))
        assert [n.message for n in history.entries()] == ["m2", "m1"]


class TestProviders:
    def test_abstract_contract(self):
        with pytest.raises(TypeError):
            NotificationProvider()  # abstract

        class Incomplete(NotificationProvider):
            @property
            def name(self):
                return "x"

        with pytest.raises(TypeError):
            Incomplete()  # send missing

    def test_null_provider_is_silent(self):
        provider = NullProvider()
        assert provider.name == "null"
        provider.send(make_notification())  # no effect, no error

    def test_console_provider_format(self):
        import io

        stream = io.StringIO()
        ConsoleProvider(stream).send(make_notification("Deep work completed"))
        assert stream.getvalue() == "- [12:00] [System] Deep work completed\n"

    def test_console_provider_critical_marker_and_errors(self):
        import io

        stream = io.StringIO()
        critical = Notification(
            category=Category.DISTURBANCE,
            title="t",
            message="fire",
            severity=Severity.CRITICAL,
            occurred_at=NOON,
        )
        ConsoleProvider(stream).send(critical)
        assert stream.getvalue().startswith("! ")
        stream.close()
        with pytest.raises(ProviderError):
            ConsoleProvider(stream).send(critical)

    def test_desktop_provider_with_injected_notifier(self):
        from paios.notifications import DesktopProvider

        calls = []
        provider = DesktopProvider(
            notifier=lambda title, message, critical: calls.append(
                (title, message, critical)
            )
        )
        provider.send(make_notification("Time to start Deep work"))
        assert calls == [("t", "Time to start Deep work", False)]

    def test_desktop_provider_unavailable_without_qapplication(self):
        from paios.notifications import (
            DesktopProvider,
            ProviderUnavailableError,
        )

        try:
            from PySide6.QtWidgets import QApplication
        except ImportError:
            pytest.skip("PySide6 not installed")
        if QApplication.instance() is not None:
            pytest.skip("a QApplication exists in this test process")
        with pytest.raises(ProviderUnavailableError):
            DesktopProvider()
