"""Context — reusable, static definition of a situational category.

Context does not carry time and does not know when it is active
(DOMAIN_MODEL.md Principle 17). It is unowned: a shared definition referenced
by many Context Windows across many Events (ENTITY_RELATIONSHIPS.md).
Because Context is static by design, it is a frozen dataclass.
"""

from dataclasses import dataclass
from datetime import datetime

from paios.domain.errors import DomainValidationError
from paios.domain.value_objects.identifiers import ContextId


@dataclass(frozen=True, slots=True)
class Context:
    context_id: ContextId
    name: str
    created_at: datetime
    location: str | None = None
    people: tuple[str, ...] = ()
    emotion: str | None = None
    trigger: str | None = None
    reason: str | None = None
    environment: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise DomainValidationError("Context requires a name")
