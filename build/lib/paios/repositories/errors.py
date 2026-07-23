"""Repository-layer exceptions.

Kept separate from the domain exception hierarchy: a persistence failure is
an infrastructure concern, never a domain-rule violation.
"""


class RepositoryError(Exception):
    """Base class for every repository-layer error."""


class SerializationError(RepositoryError):
    """Data could not be serialized to JSON or deserialized back into a
    valid domain object (corrupted file, invalid enum value, missing field,
    or a persisted transition sequence the domain state machine rejects)."""


class EntityNotFound(RepositoryError):
    """No entity with the requested identifier exists in the store."""


class DuplicateEntity(RepositoryError):
    """An entity with the same identifier is already persisted; use
    ``update`` to overwrite an existing entity."""
