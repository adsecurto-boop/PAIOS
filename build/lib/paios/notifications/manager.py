"""NotificationManager: the Event Bus observer.

Subscribes, formats, deduplicates, applies quiet hours, routes to
providers, records history. Nothing else: it holds no kernel, scheduler,
engine, or repository reference — only the bus it subscribed to and its
own providers/history. Payload entities are READ (duck-typed attribute
access, the presentation convention) and never mutated or called.

An observer must never disturb the publisher: the bus dispatches
synchronously and propagates handler exceptions to the runtime, so
every handler here is exception-tight — a formatting surprise or a
failing provider can never break a kernel broadcast.

Delivery decisions per notification:
- duplicate within the cooldown window  -> dropped entirely
- quiet hours & not critical            -> recorded (unread), not routed
- otherwise                             -> recorded and routed to every
  provider; a failing provider is isolated, the rest still deliver.
"""

from datetime import datetime

from paios.notifications.config import NotificationConfig
from paios.notifications.history import NotificationHistory
from paios.notifications.notification import Category, Notification, Severity
from paios.notifications.provider import NotificationProvider
from paios.runtime.event_bus import EventBus
from paios.runtime.system_events import SystemEvent, SystemEventType

#: Event.status -> (message template, severity). The mission's rules:
#: Ready is the "time to start" reminder; Completed the completion note.
_EVENT_STATUS_MESSAGES: dict[str, tuple[str, Severity]] = {
    "Ready": ("Time to start {description}", Severity.NORMAL),
    "Started": ("Started: {description}", Severity.NORMAL),
    "Resumed": ("Resumed: {description}", Severity.NORMAL),
    "Paused": ("Paused: {description}", Severity.NORMAL),
    "Completed": ("{description} completed", Severity.NORMAL),
    "Cancelled": ("Cancelled: {description}", Severity.NORMAL),
}


def _value(enum_like) -> str:
    """Duck-typed enum -> its value string (the serialization convention)."""
    return str(getattr(enum_like, "value", enum_like))


class NotificationManager:
    def __init__(
        self,
        config: NotificationConfig | None = None,
        providers: tuple[NotificationProvider, ...] = (),
    ) -> None:
        self._config = config if config is not None else NotificationConfig()
        self._providers = tuple(providers)
        self._history = NotificationHistory(self._config.history_limit)
        self._bus: EventBus | None = None
        self._last_sent: dict[str, datetime] = {}
        self.delivered = 0
        self.held_quiet = 0
        self.deduplicated = 0

    # --- wiring -----------------------------------------------------------

    @property
    def attached(self) -> bool:
        return self._bus is not None

    @property
    def history(self) -> NotificationHistory:
        return self._history

    @property
    def providers(self) -> tuple[NotificationProvider, ...]:
        return self._providers

    #: Bus vocabulary this observer listens to (mission event -> signal).
    SUBSCRIPTIONS: tuple[SystemEventType, ...] = (
        SystemEventType.RECOMMENDATION_GENERATED,  # RecommendationGenerated
        SystemEventType.PLAN_UPDATED,              # Accepted / Rejected
        SystemEventType.EVENT_STATE_CHANGED,       # Started/Paused/... lifecycle
        SystemEventType.RUNNING_CONTEXT_CHANGED,   # ContextChanged
        SystemEventType.DISTURBANCE_DETECTED,      # DisturbanceDetected
        SystemEventType.TIME_PROGRESSED,           # TimeProgressed
        SystemEventType.INSIGHT_GENERATED,         # LearningCompleted
        SystemEventType.REFLECTION_CREATED,        # LearningCompleted
        SystemEventType.HABIT_DETECTED,            # LearningCompleted
        SystemEventType.KERNEL_BOOTED,             # ApplicationStarted
        SystemEventType.KERNEL_SHUTDOWN,           # ApplicationStopped
    )

    def attach(self, bus: EventBus, started_at: datetime | None = None) -> None:
        """Subscribe to the bus. If ``started_at`` is given, record the
        ApplicationStarted notification directly — composition roots
        attach AFTER Application.start(), so KernelBooted has already
        been broadcast by the time this observer exists."""
        if self._bus is bus:
            return
        self.detach()
        for event_type in self.SUBSCRIPTIONS:
            bus.subscribe(event_type, self._on_event)
        self._bus = bus
        if started_at is not None:
            self._emit(
                Category.SYSTEM,
                "PAIOS",
                "Application started",
                Severity.INFO,
                started_at,
            )

    def detach(self) -> None:
        if self._bus is None:
            return
        for event_type in self.SUBSCRIPTIONS:
            self._bus.unsubscribe(event_type, self._on_event)
        self._bus = None

    # --- the observer ----------------------------------------------------

    def _on_event(self, event: SystemEvent) -> None:
        try:
            for notification in self._build(event):
                self._process(notification)
        except Exception:
            # Observer contract: never propagate into the publisher.
            pass

    def _build(self, event: SystemEvent) -> list[Notification]:
        kind = event.event_type
        payload = event.payload
        at = event.occurred_at
        make = self._notification

        if kind is SystemEventType.RECOMMENDATION_GENERATED:
            recommendation = payload.get("recommendation")
            if recommendation is None:
                return []
            return [
                make(
                    Category.RECOMMENDATION,
                    "Recommendation",
                    str(recommendation.reason),
                    Severity.NORMAL,
                    at,
                )
            ]

        if kind is SystemEventType.PLAN_UPDATED:
            notifications = []
            for recommendation in payload.get("recommendations_updated", ()):
                status = _value(getattr(recommendation, "status", None))
                if status == "Accepted":
                    text = f"Recommendation accepted: {recommendation.reason}"
                elif status == "Rejected":
                    text = f"Recommendation rejected: {recommendation.reason}"
                else:  # Consumed/Expired churn is plan bookkeeping, not news
                    continue
                notifications.append(
                    make(
                        Category.RECOMMENDATION,
                        "Recommendation",
                        text,
                        Severity.NORMAL,
                        at,
                    )
                )
            return notifications

        if kind is SystemEventType.EVENT_STATE_CHANGED:
            entity = payload.get("event")
            status = _value(getattr(entity, "status", None))
            rule = _EVENT_STATUS_MESSAGES.get(status)
            if entity is None or rule is None:
                return []
            template, severity = rule
            return [
                make(
                    Category.EVENT,
                    "Event",
                    template.format(description=entity.description),
                    severity,
                    at,
                )
            ]

        if kind is SystemEventType.RUNNING_CONTEXT_CHANGED:
            current = payload.get("current_window")
            detail = (
                f"window {str(current)[:8]}…" if current else "no active window"
            )
            return [
                make(
                    Category.CONTEXT,
                    "Context",
                    f"Context changed ({detail})",
                    Severity.INFO,
                    at,
                )
            ]

        if kind is SystemEventType.DISTURBANCE_DETECTED:
            disturber = payload.get("event_disturber")
            if disturber is None:
                return []
            severity_name = _value(getattr(disturber, "severity", None))
            return [
                make(
                    Category.DISTURBANCE,
                    "Disturbance",
                    "Unexpected interruption recorded: "
                    f"{disturber.description}",
                    (
                        Severity.CRITICAL
                        if severity_name == "High"
                        else Severity.NORMAL
                    ),
                    at,
                )
            ]

        if kind is SystemEventType.TIME_PROGRESSED:
            return [
                make(
                    Category.TIME,
                    "Time",
                    "Time progressed",
                    Severity.INFO,
                    at,
                )
            ]

        if kind is SystemEventType.INSIGHT_GENERATED:
            return [
                make(
                    Category.LEARNING,
                    "Learning",
                    "New insight generated",
                    Severity.NORMAL,
                    at,
                )
            ]

        if kind is SystemEventType.REFLECTION_CREATED:
            return [
                make(
                    Category.LEARNING,
                    "Learning",
                    "Reflection recorded",
                    Severity.INFO,
                    at,
                )
            ]

        if kind is SystemEventType.HABIT_DETECTED:
            return [
                make(
                    Category.LEARNING,
                    "Learning",
                    "New habit detected",
                    Severity.NORMAL,
                    at,
                )
            ]

        if kind is SystemEventType.KERNEL_BOOTED:
            return [
                make(
                    Category.SYSTEM,
                    "PAIOS",
                    "Application started",
                    Severity.INFO,
                    at,
                )
            ]

        if kind is SystemEventType.KERNEL_SHUTDOWN:
            return [
                make(
                    Category.SYSTEM,
                    "PAIOS",
                    "Application stopped",
                    Severity.INFO,
                    at,
                )
            ]

        return []

    # --- pipeline: dedup -> quiet hours -> route --------------------------

    def _notification(
        self,
        category: Category,
        title: str,
        message: str,
        severity: Severity,
        at: datetime,
    ) -> Notification:
        return Notification(
            category=category,
            title=title,
            message=message,
            severity=severity,
            occurred_at=at,
        )

    def _emit(self, *args) -> None:
        """Build + process directly (used for the attach-time announce)."""
        self._process(self._notification(*args))

    def _process(self, notification: Notification) -> None:
        if self._is_duplicate(notification):
            self.deduplicated += 1
            return
        self._last_sent[notification.dedup_key] = notification.occurred_at
        self._history.record(notification)
        if self._is_quiet(notification):
            self.held_quiet += 1  # kept unread in history, not routed
            return
        self._route(notification)

    def _is_duplicate(self, notification: Notification) -> bool:
        previous = self._last_sent.get(notification.dedup_key)
        if previous is None:
            return False
        elapsed = (notification.occurred_at - previous).total_seconds()
        return 0 <= elapsed < self._config.cooldown_seconds

    def _is_quiet(self, notification: Notification) -> bool:
        window = self._config.quiet_hours
        if window is None or notification.severity is Severity.CRITICAL:
            return False
        return window.contains(notification.occurred_at.time())

    def _route(self, notification: Notification) -> None:
        for provider in self._providers:
            try:
                provider.send(notification)
            except Exception:
                continue  # one failing channel never blocks the others
        self.delivered += 1
