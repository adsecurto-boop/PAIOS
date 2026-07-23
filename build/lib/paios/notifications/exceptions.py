"""Notification-layer exceptions.

These never cross into the runtime: the manager's bus handlers swallow
everything (an observer must not disturb the publisher), so these types
exist for provider construction and direct API misuse only.
"""


class NotificationError(Exception):
    """Base for the notification subsystem."""


class ProviderError(NotificationError):
    """A provider failed to deliver one notification."""


class ProviderUnavailableError(NotificationError):
    """The provider's transport does not exist in this environment
    (e.g. DesktopProvider without PySide6 or a running QApplication)."""
