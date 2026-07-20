"""Goal — Layer 3, Emergent.

Goals are not fixed objectives: they emerge from long-term Project completion
and Event history, are suggested by the Decision Engine, and require user
acceptance (DOMAIN_MODEL.md Principle 4). They represent direction, not
destination.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from paios.domain.entities.base import Entity
from paios.domain.enums import GoalStatus
from paios.domain.errors import DomainValidationError
from paios.domain.value_objects.identifiers import GoalId, ProjectId, UserId


@dataclass(eq=False)
class Goal(Entity):
    _id_attr: ClassVar[str] = "goal_id"

    goal_id: GoalId
    user_id: UserId
    name: str
    description: str
    suggested_by: str = "Decision Engine"
    accepted_by_user: bool = False
    accepted_at: datetime | None = None
    status: GoalStatus = GoalStatus.ACTIVE
    related_project_ids: tuple[ProjectId, ...] = ()
    confidence_score: float | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise DomainValidationError("Goal requires a name")

    def accept(self, at: datetime) -> None:
        """The user decides whether to accept a suggested Goal."""
        self.accepted_by_user = True
        self.accepted_at = at

    def change_status(self, status: GoalStatus) -> None:
        self.status = status
