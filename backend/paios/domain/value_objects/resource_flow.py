"""Resource Flow value object.

Resources are not simply increased or decreased: every Event consumes some
Resources and produces others (DOMAIN_MODEL.md Principle 8). The Resource Flow
is the consumed/produced breakdown attached to a single Event (GLOSSARY.md).

Amounts are positive magnitudes — direction is expressed by which side of the
flow they sit on, mirroring the storage example in ENTITY_RELATIONSHIPS.md
(consumed: {time: 120, energy: 20} / produced: {knowledge: 35, career: 25}).
"""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from paios.domain.enums import ResourceType
from paios.domain.errors import DomainValidationError


@dataclass(frozen=True)
class ResourceFlow:
    """Immutable consumed/produced Resource breakdown for one Event."""

    consumed: Mapping[ResourceType, float] = field(default_factory=dict)
    produced: Mapping[ResourceType, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for side_name in ("consumed", "produced"):
            side = getattr(self, side_name)
            for resource_type, amount in side.items():
                if not isinstance(resource_type, ResourceType):
                    raise DomainValidationError(
                        f"ResourceFlow.{side_name} keys must be ResourceType"
                    )
                if not isinstance(amount, (int, float)) or isinstance(amount, bool):
                    raise DomainValidationError(
                        f"ResourceFlow.{side_name} amounts must be numbers"
                    )
                if amount <= 0:
                    raise DomainValidationError(
                        f"ResourceFlow.{side_name} amounts must be positive "
                        "magnitudes; direction is expressed by the flow side"
                    )
            object.__setattr__(self, side_name, MappingProxyType(dict(side)))

    @classmethod
    def empty(cls) -> "ResourceFlow":
        return cls()

    @property
    def is_empty(self) -> bool:
        return not self.consumed and not self.produced
