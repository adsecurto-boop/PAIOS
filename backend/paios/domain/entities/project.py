"""Project — an intentional body of work (DOMAIN_MODEL.md Principle 3).

Owned by the User; owns exactly one Progress (referenced by ID here — the
Progress entity itself lives in progress.py). Projects are NOT Goals.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from paios.domain.entities.base import Entity
from paios.domain.enums import ProjectStatus
from paios.domain.errors import DomainValidationError
from paios.domain.value_objects.identifiers import ProgressId, ProjectId, UserId


@dataclass(eq=False)
class Project(Entity):
    _id_attr: ClassVar[str] = "project_id"

    project_id: ProjectId
    user_id: UserId
    name: str
    description: str
    created_at: datetime
    progress_id: ProgressId | None = None
    status: ProjectStatus = ProjectStatus.ACTIVE

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise DomainValidationError("Project requires a name")

    def change_status(self, status: ProjectStatus) -> None:
        self.status = status

    def attach_progress(self, progress_id: ProgressId) -> None:
        """Progress belongs to exactly one Project (BUSINESS_RULES.md)."""
        if self.progress_id is not None and self.progress_id != progress_id:
            raise DomainValidationError(
                "Project already owns a Progress; it cannot own another"
            )
        self.progress_id = progress_id
