"""GUI notification center: history + unread state + a poll-diff watcher.

The M13 GUI is REST-only and imports nothing from the backend, so its
notification center observes the only thing it can see: successive REST
poll payloads. The watcher diffs consecutive `/dashboard` responses and
reports what changed — new recommendations, a new running event, new
disturbers, a context switch. That is presentation diffing (comparing
ids the API already sent), not business logic.

Qt-free module: the center and watcher are plain Python (testable
without a QApplication); the page and tray toast live with the widgets.
"""

from dataclasses import dataclass, field
from itertools import count

_sequence = count(1)


@dataclass
class GuiNotification:
    message: str
    category: str
    kind: str = "info"  # info | ok | warn | error
    occurred_at: str = ""  # display string (API time or local clock)
    read: bool = False
    notification_id: int = field(default_factory=lambda: next(_sequence))


class NotificationCenter:
    """Bounded, newest-first notification history with unread tracking."""

    def __init__(self, limit: int = 200) -> None:
        self._limit = max(1, limit)
        self._entries: list[GuiNotification] = []

    def add(self, notification: GuiNotification) -> None:
        self._entries.insert(0, notification)
        del self._entries[self._limit:]

    def entries(self) -> list[GuiNotification]:
        return list(self._entries)

    @property
    def unread_count(self) -> int:
        return sum(1 for n in self._entries if not n.read)

    def mark_all_read(self) -> int:
        marked = 0
        for notification in self._entries:
            if not notification.read:
                notification.read = True
                marked += 1
        return marked

    def clear(self) -> int:
        dropped = len(self._entries)
        self._entries.clear()
        return dropped


class DashboardWatcher:
    """Diffs consecutive /dashboard payloads into GuiNotifications.

    The first observation is the baseline: it reports nothing (opening
    the app must not replay the whole current state as 'news')."""

    def __init__(self) -> None:
        self._baseline_taken = False
        self._recommendation_ids: set[str] = set()
        self._disturber_ids: set[str] = set()
        self._running_event_id: str | None = None
        self._execution_context: str | None = None

    def observe(self, dashboard: dict) -> list[GuiNotification]:
        at = _clock(dashboard.get("current_time"))
        recommendations = dashboard.get("recommendations") or []
        disturbers = dashboard.get("active_disturbers") or []
        current_event = dashboard.get("current_event")
        context = dashboard.get("current_context") or {}

        recommendation_ids = {
            r["recommendation_id"] for r in recommendations
        }
        disturber_ids = {d["event_disturber_id"] for d in disturbers}
        running_id = current_event["event_id"] if current_event else None
        execution_context = context.get("execution_context")

        fresh: list[GuiNotification] = []
        if self._baseline_taken:
            for recommendation in recommendations:
                if recommendation["recommendation_id"] in self._recommendation_ids:
                    continue
                fresh.append(
                    GuiNotification(
                        message=f"Recommendation: {recommendation['reason']}",
                        category="Recommendation",
                        kind="info",
                        occurred_at=at,
                    )
                )
            for disturber in disturbers:
                if disturber["event_disturber_id"] in self._disturber_ids:
                    continue
                fresh.append(
                    GuiNotification(
                        message=(
                            "Disturbance: "
                            f"[{disturber['severity']}] {disturber['description']}"
                        ),
                        category="Disturbance",
                        kind=(
                            "error"
                            if disturber["severity"] == "High"
                            else "warn"
                        ),
                        occurred_at=at,
                    )
                )
            if running_id != self._running_event_id and current_event:
                fresh.append(
                    GuiNotification(
                        message=f"Now running: {current_event['description']}",
                        category="Event",
                        kind="ok",
                        occurred_at=at,
                    )
                )
            if (
                execution_context != self._execution_context
                and execution_context is not None
            ):
                fresh.append(
                    GuiNotification(
                        message=f"Context changed: {execution_context}",
                        category="Context",
                        kind="info",
                        occurred_at=at,
                    )
                )

        self._baseline_taken = True
        self._recommendation_ids = recommendation_ids
        self._disturber_ids = disturber_ids
        self._running_event_id = running_id
        self._execution_context = execution_context
        return fresh


def _clock(iso: str | None) -> str:
    if not iso:
        return ""
    return iso.split("T")[1][:5] if "T" in iso else iso[:5]
