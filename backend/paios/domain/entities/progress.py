"""Progress — a first-class entity owned by exactly one Project
(DOMAIN_MODEL.md Principle 12; BUSINESS_RULES.md - Progress Rules).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from paios.domain.entities.base import Entity
from paios.domain.errors import DomainValidationError
from paios.domain.value_objects.identifiers import ProgressId, ProjectId


@dataclass(eq=False)
class Progress(Entity):
    _id_attr: ClassVar[str] = "progress_id"

    progress_id: ProgressId
    project_id: ProjectId
    completion_percentage: float = 0.0
    knowledge_gained: float = 0.0
    habit_score: float = 0.0
    resource_delta: float = 0.0
    velocity: float = 0.0
    estimated_completion: datetime | None = None
    confidence: float = 0.0
    last_updated: datetime | None = None

    def __post_init__(self) -> None:
        self._validate_completion(self.completion_percentage)

    @staticmethod
    def _validate_completion(value: float) -> None:
        if not 0.0 <= value <= 100.0:
            raise DomainValidationError(
                "Completion percentage must be between 0 and 100"
            )

    def update(
        self,
        at: datetime,
        *,
        completion_percentage: float | None = None,
        knowledge_gained: float | None = None,
        habit_score: float | None = None,
        resource_delta: float | None = None,
        velocity: float | None = None,
        estimated_completion: datetime | None = None,
        confidence: float | None = None,
    ) -> None:
        """Progress changes over time as Events complete within the Project."""
        if completion_percentage is not None:
            self._validate_completion(completion_percentage)
            self.completion_percentage = completion_percentage
        if knowledge_gained is not None:
            self.knowledge_gained = knowledge_gained
        if habit_score is not None:
            self.habit_score = habit_score
        if resource_delta is not None:
            self.resource_delta = resource_delta
        if velocity is not None:
            self.velocity = velocity
        if estimated_completion is not None:
            self.estimated_completion = estimated_completion
        if confidence is not None:
            self.confidence = confidence
        self.last_updated = at
