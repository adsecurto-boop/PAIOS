"""Application-layer exceptions."""


class ApplicationError(Exception):
    """Base class for application-layer errors."""


class ApplicationNotStartedError(ApplicationError):
    """The operation requires a started application."""


class ApplicationAlreadyStartedError(ApplicationError):
    """start() was called on an application that is already running."""


class DuplicateEntityError(ApplicationError):
    """An equivalent entity already exists (Milestone 10 duplicate
    detection — an orchestration guard over ``find_by``, not a domain
    rule)."""


class ProgressNotAttachedError(ApplicationError):
    """The Project owns no Progress entity to update."""
