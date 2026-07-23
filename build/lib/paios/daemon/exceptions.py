"""Daemon exceptions."""


class DaemonError(Exception):
    """Base class for daemon-layer errors."""


class DaemonStateError(DaemonError):
    """The operation is not permitted in the daemon's current state."""


class ClockAdvanceError(DaemonError):
    """The clock cannot be advanced (SystemClock) or the target moment
    would move time backwards — runtime time advances monotonically
    (RUNTIME_EXECUTION.md - Consistency Guarantees)."""
