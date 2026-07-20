"""Application-layer exceptions."""


class ApplicationError(Exception):
    """Base class for application-layer errors."""


class ApplicationNotStartedError(ApplicationError):
    """The operation requires a started application."""


class ApplicationAlreadyStartedError(ApplicationError):
    """start() was called on an application that is already running."""
