"""Learning-layer exceptions."""


class LearningError(Exception):
    """Base class for learning-layer errors."""


class InvalidHistoryError(LearningError):
    """The supplied history is not analyzable (e.g. not a History view)."""
