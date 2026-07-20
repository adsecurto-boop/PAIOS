"""PAIOS Repository Layer (Milestone 2).

JSON persistence for the domain aggregates, following the Repository
Pattern. Repositories depend on the Domain; the Domain never depends on
repositories. Repositories only persist — no business logic, no runtime
behavior, no clock access.

Storage: one JSON array file per aggregate inside `.data/`
(ENTITY_RELATIONSHIPS.md - Local Data Storage). Runtime data is never
committed to git.
"""

from paios.repositories.errors import (
    DuplicateEntity,
    EntityNotFound,
    RepositoryError,
    SerializationError,
)
from paios.repositories.factory import RepositoryFactory
from paios.repositories.json_store import JsonStore

__all__ = [
    "DuplicateEntity",
    "EntityNotFound",
    "JsonStore",
    "RepositoryError",
    "RepositoryFactory",
    "SerializationError",
]
