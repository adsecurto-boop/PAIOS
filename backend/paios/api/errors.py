"""Exception -> HTTP translation.

The API imports exception TYPES from the layers whose errors legitimately
cross the facade boundary (the documented M10 contract: domain and
repository errors propagate unchanged through the Application). Importing
an exceptions module is not importing behavior — no runtime, scheduler,
decision-engine, learning, or repository *implementation* module is
touched. Runtime exceptions (e.g. RuntimeInvariantError) cannot be
imported here at all; they fall to the generic 500 handler by class-name
fallback, keeping the forbidden-import rule absolute.
"""

from paios.application.exceptions import (
    ApplicationError,
    ApplicationNotStartedError,
    DuplicateEntityError,
    ProgressNotAttachedError,
)
from paios.domain.errors import (
    DomainError,
    DomainValidationError,
    ImmutabilityViolationError,
    InvalidTransitionError,
    InvariantViolationError,
)
from paios.repositories.errors import EntityNotFound, RepositoryError


class ApiError(Exception):
    """A transport-level error: bad syntax, unknown route, bad method."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


#: Most specific class first — the first isinstance match wins.
_EXCEPTION_STATUS: tuple[tuple[type, int], ...] = (
    (EntityNotFound, 404),
    (DuplicateEntityError, 409),
    (ProgressNotAttachedError, 409),
    (InvalidTransitionError, 409),  # includes RecommendationExpiredError
    (ImmutabilityViolationError, 409),
    (InvariantViolationError, 409),
    (DomainValidationError, 400),
    (ApplicationNotStartedError, 503),
    (DomainError, 400),
    (RepositoryError, 500),
    (ApplicationError, 500),
)


def payload(status: int, error_type: str, message: str) -> dict:
    return {"error": {"type": error_type, "message": message}}


def translate(error: Exception) -> tuple[int, dict]:
    """Map any raised exception to (HTTP status, JSON error payload)."""
    if isinstance(error, ApiError):
        return error.status, payload(
            error.status, type(error).__name__, str(error)
        )
    for exception_type, status in _EXCEPTION_STATUS:
        if isinstance(error, exception_type):
            return status, payload(status, type(error).__name__, str(error))
    # Unimportable layers (e.g. paios.runtime's RuntimeInvariantError) and
    # anything unexpected: an opaque 500, name preserved for diagnosis.
    return 500, payload(500, type(error).__name__, str(error))
