"""PAIOS notification subsystem — an Event Bus observer (Milestone 14).

Event Bus -> NotificationManager -> providers (console / desktop / null).

The subsystem reacts to published SystemEvents and does nothing else:
no business logic, no Runtime/Scheduler/Decision-Engine/Learning
mutations, no persistence. It reads event payloads to format messages,
throttles duplicates, applies quiet hours, and keeps an in-memory
history with unread tracking.
"""

from paios.notifications.config import NotificationConfig, QuietHours
from paios.notifications.console_provider import ConsoleProvider
from paios.notifications.desktop_provider import DesktopProvider
from paios.notifications.exceptions import (
    NotificationError,
    ProviderError,
    ProviderUnavailableError,
)
from paios.notifications.history import NotificationHistory
from paios.notifications.manager import NotificationManager
from paios.notifications.notification import Category, Notification, Severity
from paios.notifications.provider import NotificationProvider, NullProvider

__all__ = [
    "Category",
    "ConsoleProvider",
    "DesktopProvider",
    "Notification",
    "NotificationConfig",
    "NotificationError",
    "NotificationHistory",
    "NotificationManager",
    "NotificationProvider",
    "NullProvider",
    "ProviderError",
    "ProviderUnavailableError",
    "QuietHours",
    "Severity",
]
