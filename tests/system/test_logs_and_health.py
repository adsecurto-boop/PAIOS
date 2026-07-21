"""Structured logging (setup, bus observer, log provider) and health."""

import logging
from datetime import datetime

from paios.notifications.notification import Category, Notification, Severity
from paios.runtime.event_bus import EventBus
from paios.runtime.system_events import SystemEvent, SystemEventType
from paios.system import (
    BusLogObserver,
    LogProvider,
    run_health_checks,
    setup_logging,
)
from paios.system.config import SystemConfig

NOON = datetime(2026, 7, 22, 12, 0)


def read_log(log_dir, component) -> str:
    for handler in logging.getLogger("paios").handlers:
        handler.flush()
    return (log_dir / f"paios-{component}.log").read_text(encoding="utf-8")


class TestSetup:
    def test_writes_structured_lines(self, tmp_path):
        logger = setup_logging(tmp_path, "cli")
        logger.info("hello key=%s", "value")
        line = read_log(tmp_path, "cli").strip()
        parts = [part.strip() for part in line.split("|")]
        assert parts[1] == "INFO"
        assert parts[2] == "paios.cli"
        assert parts[3] == "hello key=value"

    def test_reconfiguration_replaces_the_handler(self, tmp_path):
        setup_logging(tmp_path / "a", "cli")
        logging.getLogger("paios.cli").info("first")
        setup_logging(tmp_path / "b", "daemon")
        logging.getLogger("paios.daemon").info("second")
        assert "second" in read_log(tmp_path / "b", "daemon")
        assert len(logging.getLogger("paios").handlers) == 1


class TestBusLogObserver:
    def test_scheduler_and_runtime_events_logged(self, tmp_path):
        setup_logging(tmp_path, "daemon")
        bus = EventBus()
        observer = BusLogObserver()
        observer.attach(bus)
        bus.publish(
            SystemEvent(
                SystemEventType.PLAN_UPDATED, NOON, {"reason": "TimeProgressed"}
            )
        )
        bus.publish(SystemEvent(SystemEventType.KERNEL_BOOTED, NOON, {}))
        text = read_log(tmp_path, "daemon")
        assert "paios.scheduler" in text and "event=PlanUpdated" in text
        assert "reason=TimeProgressed" in text
        assert "paios.runtime" in text and "event=KernelBooted" in text

    def test_detach_and_observer_safety(self, tmp_path):
        setup_logging(tmp_path, "daemon")
        bus = EventBus()
        observer = BusLogObserver()
        observer.attach(bus)
        observer.attach(bus)  # idempotent
        assert bus.subscriber_count(SystemEventType.PLAN_UPDATED) == 1
        observer.detach()
        assert bus.subscriber_count(SystemEventType.PLAN_UPDATED) == 0

    def test_never_disturbs_the_publisher(self, tmp_path):
        bus = EventBus()
        observer = BusLogObserver()
        observer.attach(bus)
        observer._scheduler_log = None  # force an internal failure
        bus.publish(
            SystemEvent(SystemEventType.PLAN_UPDATED, NOON, {})
        )  # must not raise


class TestLogProvider:
    def test_notifications_reach_the_log(self, tmp_path):
        setup_logging(tmp_path, "cli")
        LogProvider().send(
            Notification(
                category=Category.EVENT,
                title="Event",
                message="Deep work completed",
                severity=Severity.NORMAL,
                occurred_at=NOON,
            )
        )
        text = read_log(tmp_path, "cli")
        assert "paios.notifications" in text
        assert "category=Event" in text
        assert "message=Deep work completed" in text


class TestHealth:
    def test_healthy_fresh_install(self, tmp_path):
        config = SystemConfig(
            data_dir=str(tmp_path / "data"),
            log_dir=str(tmp_path / "logs"),
            backup_dir=str(tmp_path / "backups"),
            server_port=1,  # nothing listens; reported as "not serving"
        )
        checks = run_health_checks(config)
        components = [check.component for check in checks]
        assert components == [
            "repositories",
            "application",
            "scheduler",
            "clock",
            "event bus",
            "daemon",
            "api",
        ]
        assert all(check.ok for check in checks), [
            (c.component, c.detail) for c in checks if not c.ok
        ]

    def test_broken_store_file_fails_repositories(self, tmp_path):
        data = tmp_path / "data"
        data.mkdir()
        (data / "events.json").write_text("{not json", encoding="utf-8")
        config = SystemConfig(data_dir=str(data))
        checks = run_health_checks(config, include_api=False)
        repositories = checks[0]
        assert repositories.component == "repositories"
        assert repositories.ok is False
        assert "events.json" in repositories.detail
