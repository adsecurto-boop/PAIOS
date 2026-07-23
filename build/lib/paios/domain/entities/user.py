"""User — the ownership anchor of Layer 2.

The User owns Projects, Events, Scheduler state, Resources, Knowledge,
Recommendations, Habits, Insights, and Goals — but follows rather than owns
Principles, and does not own Context (DOMAIN_MODEL.md / GLOSSARY.md).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from paios.domain.entities.base import Entity
from paios.domain.errors import DomainValidationError
from paios.domain.value_objects.identifiers import UserId


@dataclass(eq=False)
class User(Entity):
    _id_attr: ClassVar[str] = "user_id"

    user_id: UserId
    name: str
    created_at: datetime
    last_active: datetime | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise DomainValidationError("User requires a name")

    def record_activity(self, at: datetime) -> None:
        self.last_active = at
