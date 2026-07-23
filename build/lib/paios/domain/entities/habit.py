"""Habit — Layer 3, Emergent.

Habits cannot be manually created; they are inferred from repeated Events and
never own Events (BUSINESS_RULES.md - Habit Rules). The domain expresses this
by exposing ``Habit.infer`` as the sole intended creation path — the actual
inference (pattern detection over Event history) is a Domain Policy applied
by later layers, never by this entity.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from paios.domain.entities.base import Entity
from paios.domain.errors import DomainValidationError
from paios.domain.value_objects.identifiers import HabitId, UserId


@dataclass(eq=False)
class Habit(Entity):
    _id_attr: ClassVar[str] = "habit_id"

    habit_id: HabitId
    user_id: UserId
    name: str
    detected_at: datetime
    trigger: str | None = None
    frequency: str | None = None
    reward: str | None = None
    current_trend: str | None = None
    strength: float = 0.0
    desired_state: str | None = None
    last_updated: datetime | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise DomainValidationError("Habit requires a name")
        self._validate_strength(self.strength)

    @staticmethod
    def _validate_strength(value: float) -> None:
        if not 0.0 <= value <= 100.0:
            raise DomainValidationError("Habit strength must be between 0 and 100")

    @classmethod
    def infer(
        cls,
        habit_id: HabitId,
        user_id: UserId,
        name: str,
        detected_at: datetime,
        *,
        trigger: str | None = None,
        frequency: str | None = None,
        reward: str | None = None,
        strength: float = 0.0,
    ) -> "Habit":
        """The sole intended creation path: Habits emerge from Event history,
        they are never manually created."""
        return cls(
            habit_id=habit_id,
            user_id=user_id,
            name=name,
            detected_at=detected_at,
            trigger=trigger,
            frequency=frequency,
            reward=reward,
            strength=strength,
        )

    def update_strength(self, strength: float, at: datetime) -> None:
        self._validate_strength(strength)
        self.strength = strength
        self.last_updated = at
