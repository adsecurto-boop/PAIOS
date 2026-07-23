"""Domain-layer exceptions.

Every rule violation in the domain layer raises a subclass of DomainError,
so callers can distinguish domain-rule failures from programming errors.
"""


class DomainError(Exception):
    """Base class for every domain-layer error."""


class DomainValidationError(DomainError):
    """A value or field violates its own structural validation rules."""


class InvalidTransitionError(DomainError):
    """A state transition not permitted by the governing state machine
    (STATE_MACHINES.md formal transition tables)."""


class ImmutabilityViolationError(DomainError):
    """An attempt to rewrite immutable History — e.g. mutating a Completed
    Event or reassigning an Event ID (BUSINESS_RULES.md - Domain Invariants)."""


class InvariantViolationError(DomainError):
    """A Domain Invariant does not hold (BUSINESS_RULES.md - Domain Invariants)."""


class RecommendationExpiredError(InvalidTransitionError):
    """An expired Recommendation cannot be accepted
    (BUSINESS_RULES.md - Recommendation Rules)."""
