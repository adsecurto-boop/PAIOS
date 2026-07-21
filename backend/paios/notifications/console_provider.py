"""ConsoleProvider: notifications as single lines on a text stream."""

import sys
from typing import TextIO

from paios.notifications.exceptions import ProviderError
from paios.notifications.notification import Notification
from paios.notifications.provider import NotificationProvider


class ConsoleProvider(NotificationProvider):
    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = stream

    @property
    def name(self) -> str:
        return "console"

    def send(self, notification: Notification) -> None:
        stream = self._stream if self._stream is not None else sys.stdout
        marker = "!" if notification.severity.value == "Critical" else "-"
        try:
            stream.write(
                f"{marker} [{notification.occurred_at.strftime('%H:%M')}]"
                f" [{notification.category.value}] {notification.message}\n"
            )
            stream.flush()
        except (OSError, ValueError) as error:  # closed/broken stream
            raise ProviderError(f"console write failed: {error}") from error
