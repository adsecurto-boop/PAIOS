"""The provider abstraction: one delivery channel per provider.

A provider does transport only — it receives a fully formatted
Notification and puts it somewhere a human will see it. Providers never
filter, format, or decide; the manager already did (quiet hours,
deduplication, message text). Future providers (Android, Discord,
Email, Push) implement the same two members.
"""

from abc import ABC, abstractmethod

from paios.notifications.notification import Notification


class NotificationProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Stable channel name (diagnostics and configuration)."""

    @abstractmethod
    def send(self, notification: Notification) -> None:
        """Deliver one notification. Raise ProviderError on failure —
        the manager isolates it; other providers still deliver."""


class NullProvider(NotificationProvider):
    """The silent sink: notifications route nowhere (history still
    records them). The default when no channel is configured."""

    @property
    def name(self) -> str:
        return "null"

    def send(self, notification: Notification) -> None:
        """Deliberately nothing."""
