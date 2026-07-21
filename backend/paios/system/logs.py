"""Structured logging for every PAIOS surface.

One pipe-delimited line per record:

    2026-07-22T09:00:00 | INFO | paios.cli | message | key=value ...

Components log through child loggers (paios.cli, paios.api,
paios.daemon, paios.gui, paios.scheduler, paios.notifications). The
frozen layers are never modified to log — their activity is observed:

- BusLogObserver subscribes to the System Event Bus (the M14 pattern)
  and logs kernel/scheduler broadcasts to paios.scheduler / paios.runtime.
- LogProvider is a NotificationProvider (M14 abstraction) that logs
  every delivered notification to paios.notifications.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from paios.notifications.notification import Notification
from paios.notifications.provider import NotificationProvider
from paios.runtime.event_bus import EventBus
from paios.runtime.system_events import SystemEvent, SystemEventType

_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
_MAX_BYTES = 1_000_000
_BACKUP_COUNT = 3

#: Event types originated by the Scheduler vs the Kernel/runtime.
_SCHEDULER_EVENTS = {
    SystemEventType.PLAN_UPDATED,
    SystemEventType.SCHEDULER_RECALCULATION_REQUESTED,
    SystemEventType.EVENT_STATE_CHANGED,
    SystemEventType.RECOMMENDATION_GENERATED,
}


def setup_logging(
    log_dir: str | Path, component: str, level: int = logging.INFO
) -> logging.Logger:
    """Configure the 'paios' root logger to write ``paios-<component>.log``
    in ``log_dir`` (rotating, 1 MB x 3). Idempotent per process: calling
    again replaces the file handler (tests re-point it freely). Returns
    the component's child logger."""
    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger("paios")
    root.setLevel(level)
    root.propagate = False
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    handler = RotatingFileHandler(
        directory / f"paios-{component}.log",
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT))
    root.addHandler(handler)
    return logging.getLogger(f"paios.{component}")


class BusLogObserver:
    """Logs every System Event Bus broadcast; observer only.

    Handlers are exception-tight for the same reason the notification
    manager's are: the bus dispatches synchronously inside the kernel."""

    def __init__(self) -> None:
        self._bus: EventBus | None = None
        self._scheduler_log = logging.getLogger("paios.scheduler")
        self._runtime_log = logging.getLogger("paios.runtime")

    @property
    def attached(self) -> bool:
        return self._bus is not None

    def attach(self, bus: EventBus) -> None:
        if self._bus is bus:
            return
        self.detach()
        for event_type in SystemEventType:
            bus.subscribe(event_type, self._on_event)
        self._bus = bus

    def detach(self) -> None:
        if self._bus is None:
            return
        for event_type in SystemEventType:
            self._bus.unsubscribe(event_type, self._on_event)
        self._bus = None

    def _on_event(self, event: SystemEvent) -> None:
        try:
            logger = (
                self._scheduler_log
                if event.event_type in _SCHEDULER_EVENTS
                else self._runtime_log
            )
            detail = " ".join(
                f"{key}={_compact(value)}"
                for key, value in sorted(event.payload.items())
            )
            logger.info(
                "event=%s at=%s%s",
                event.event_type.value,
                event.occurred_at.isoformat(),
                f" {detail}" if detail else "",
            )
        except Exception:
            pass  # observers never disturb the publisher


def _compact(value) -> str:
    """Payload values may be domain entities; log a short identity, not
    a dump (and never call anything on them)."""
    text = str(value)
    return text if len(text) <= 60 else text[:57] + "..."


class LogProvider(NotificationProvider):
    """Routes delivered notifications into the structured log."""

    @property
    def name(self) -> str:
        return "log"

    def send(self, notification: Notification) -> None:
        logging.getLogger("paios.notifications").info(
            "category=%s severity=%s message=%s",
            notification.category.value,
            notification.severity.value,
            notification.message,
        )
