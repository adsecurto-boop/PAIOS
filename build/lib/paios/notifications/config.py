"""Notification configuration: quiet hours, cooldown, history size."""

from dataclasses import dataclass
from datetime import time


@dataclass(frozen=True)
class QuietHours:
    """A daily window in which non-critical notifications are held back.

    Supports windows that cross midnight (the mission's 22:00-07:00)."""

    start: time
    end: time

    def contains(self, moment: time) -> bool:
        if self.start <= self.end:
            return self.start <= moment < self.end
        return moment >= self.start or moment < self.end

    @classmethod
    def parse(cls, text: str) -> "QuietHours":
        """'22:00-07:00' -> QuietHours(22:00, 07:00)."""
        try:
            start_text, end_text = text.split("-")
            return cls(time.fromisoformat(start_text), time.fromisoformat(end_text))
        except ValueError as error:
            raise ValueError(
                f"Quiet hours must look like '22:00-07:00', got {text!r}"
            ) from error


@dataclass(frozen=True)
class NotificationConfig:
    #: Daily hold-back window; None disables quiet hours.
    quiet_hours: QuietHours | None = None
    #: Seconds during which an identical notification is not repeated.
    cooldown_seconds: int = 300
    #: Ring-buffer capacity of the in-memory history.
    history_limit: int = 200
