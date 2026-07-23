"""In-memory notification history: bounded, ordered, unread-aware.

Presentation state only — never persisted (the notification system owns
no files; restart starts a fresh history)."""

from collections import deque

from paios.notifications.notification import Notification


class NotificationHistory:
    def __init__(self, limit: int = 200) -> None:
        self._entries: deque[Notification] = deque(maxlen=max(1, limit))

    def record(self, notification: Notification) -> None:
        self._entries.append(notification)

    def entries(self) -> list[Notification]:
        """All retained notifications, newest first."""
        return list(reversed(self._entries))

    def unread(self) -> list[Notification]:
        return [n for n in self.entries() if not n.read]

    @property
    def unread_count(self) -> int:
        return sum(1 for n in self._entries if not n.read)

    def mark_all_read(self) -> int:
        """Returns how many notifications were newly marked."""
        marked = 0
        for notification in self._entries:
            if not notification.read:
                notification.read = True
                marked += 1
        return marked

    def clear(self) -> int:
        """Empty the history; returns how many entries were dropped."""
        dropped = len(self._entries)
        self._entries.clear()
        return dropped

    def __len__(self) -> int:
        return len(self._entries)
