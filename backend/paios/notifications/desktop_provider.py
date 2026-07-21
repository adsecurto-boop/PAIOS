"""DesktopProvider: native desktop toasts through Qt's system tray.

PySide6 is the GUI tier's dependency (M13), not the backend's — so it
is imported lazily and only here. Constructing the provider in an
environment without PySide6 (or without a QApplication to host the tray
icon) raises ProviderUnavailableError; composition roots catch it and
fall back to another provider.

A pre-built notifier callable can be injected (the M13 GUI passes its
own tray icon's showMessage; tests pass a recorder) — then Qt is not
touched at all.
"""

from typing import Callable

from paios.notifications.exceptions import (
    ProviderError,
    ProviderUnavailableError,
)
from paios.notifications.notification import Notification, Severity
from paios.notifications.provider import NotificationProvider

#: (title, message, critical) -> None
Notifier = Callable[[str, str, bool], None]

#: Tray balloon linger time.
_TIMEOUT_MS = 6000


class DesktopProvider(NotificationProvider):
    def __init__(self, notifier: Notifier | None = None) -> None:
        self._notify = (
            notifier if notifier is not None else _tray_notifier()
        )

    @property
    def name(self) -> str:
        return "desktop"

    def send(self, notification: Notification) -> None:
        try:
            self._notify(
                notification.title,
                notification.message,
                notification.severity is Severity.CRITICAL,
            )
        except Exception as error:
            raise ProviderError(f"desktop toast failed: {error}") from error


def _tray_notifier() -> Notifier:
    """Build a notifier over a QSystemTrayIcon owned by this provider."""
    try:
        from PySide6.QtWidgets import QApplication, QSystemTrayIcon
    except ImportError as error:
        raise ProviderUnavailableError(
            "DesktopProvider needs PySide6 (the M13 GUI dependency)"
        ) from error
    if QApplication.instance() is None:
        raise ProviderUnavailableError(
            "DesktopProvider needs a running QApplication"
        )
    if not QSystemTrayIcon.isSystemTrayAvailable():
        raise ProviderUnavailableError("No system tray on this desktop")

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QStyle

    application = QApplication.instance()
    icon: QIcon = application.style().standardIcon(
        QStyle.StandardPixmap.SP_MessageBoxInformation
    )
    tray = QSystemTrayIcon(icon)
    tray.setToolTip("PAIOS")
    tray.show()

    def notify(title: str, message: str, critical: bool) -> None:
        tray.showMessage(
            title,
            message,
            (
                QSystemTrayIcon.MessageIcon.Critical
                if critical
                else QSystemTrayIcon.MessageIcon.Information
            ),
            _TIMEOUT_MS,
        )

    return notify
