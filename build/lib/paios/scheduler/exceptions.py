"""Scheduler-layer exceptions."""


class SchedulerError(Exception):
    """Base class for every scheduler-layer error."""


class SchedulerLifecycleError(SchedulerError):
    """An operation is not permitted in the Scheduler's current state."""


class SchedulingConflictError(SchedulerError):
    """A plan would violate scheduling constraints (e.g. overlapping
    future slots for one User)."""


class UnknownWorkError(SchedulerError):
    """The referenced Event or Recommendation is not in Runtime State."""
