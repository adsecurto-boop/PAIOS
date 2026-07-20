"""Principle — Layer 1, Foundation.

Principles are timeless, immutable rules representing Dharma
(DOMAIN_MODEL.md Principle 1). They are NOT owned by the User; users follow
Principles. Principles never evolve — that is what separates a Principle from
a Domain Policy.

Modelled as a frozen dataclass: immutability is structural. Reviewing a
Principle produces a new value with an updated ``last_reviewed`` — a
deliberate User action, never an AI edit (DOMAIN_MODEL.md - Principle
Immutability and Universality). Note there is intentionally no ``user_id``
field: Principles are foundational and unowned (ENTITY_RELATIONSHIPS.md).
"""

import dataclasses
from dataclasses import dataclass
from datetime import datetime

from paios.domain.enums import PrincipleCategory
from paios.domain.errors import DomainValidationError
from paios.domain.value_objects.identifiers import PrincipleId


@dataclass(frozen=True, slots=True)
class Principle:
    principle_id: PrincipleId
    name: str
    description: str
    category: PrincipleCategory
    created_at: datetime
    last_reviewed: datetime | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise DomainValidationError("Principle requires a name")

    def reviewed(self, at: datetime) -> "Principle":
        """Return a copy marking a deliberate User review; nothing else changes."""
        return dataclasses.replace(self, last_reviewed=at)
