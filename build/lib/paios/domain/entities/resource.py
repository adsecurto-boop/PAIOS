"""Resource — a quantity consumed and produced through Events
(DOMAIN_MODEL.md Principle 8).

Domain Invariant: Resources cannot become invalid — negative where a
negative value is not meaningful (BUSINESS_RULES.md). The invariant's
"where meaningful" clause is modelled by ``negative_allowed``.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from paios.domain.entities.base import Entity
from paios.domain.enums import ResourceType
from paios.domain.errors import DomainValidationError, InvariantViolationError
from paios.domain.value_objects.identifiers import ResourceId, UserId


@dataclass(eq=False)
class Resource(Entity):
    _id_attr: ClassVar[str] = "resource_id"

    resource_id: ResourceId
    user_id: UserId
    type: ResourceType
    current_value: float
    unit: str
    negative_allowed: bool = False
    last_updated: datetime | None = None

    def __post_init__(self) -> None:
        if not self.negative_allowed and self.current_value < 0:
            raise InvariantViolationError(
                f"Resource {self.type.value} cannot start with an invalid "
                "(negative) value"
            )

    def consume(self, amount: float, at: datetime) -> None:
        self._validate_amount(amount)
        new_value = self.current_value - amount
        if new_value < 0 and not self.negative_allowed:
            raise InvariantViolationError(
                f"Consuming {amount} would make Resource {self.type.value} "
                "invalid (negative where a negative value is not meaningful)"
            )
        self.current_value = new_value
        self.last_updated = at

    def produce(self, amount: float, at: datetime) -> None:
        self._validate_amount(amount)
        self.current_value += amount
        self.last_updated = at

    @staticmethod
    def _validate_amount(amount: float) -> None:
        if amount <= 0:
            raise DomainValidationError(
                "Resource amounts must be positive magnitudes"
            )
