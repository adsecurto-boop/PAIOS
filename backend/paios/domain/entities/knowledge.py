"""Knowledge — tracked learning and skill acquisition (DOMAIN_MODEL.md
Principle 9). Owned by the User, belongs primarily to Projects, and changes
over time through revision, application, and retention decay (Principle 16).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from paios.domain.entities.base import Entity
from paios.domain.errors import DomainValidationError
from paios.domain.value_objects.identifiers import KnowledgeId, ProjectId, UserId


@dataclass(eq=False)
class Knowledge(Entity):
    _id_attr: ClassVar[str] = "knowledge_id"

    knowledge_id: KnowledgeId
    user_id: UserId
    domain: str
    topic: str
    concept: str
    project_id: ProjectId | None = None
    difficulty: str | None = None
    confidence: float = 0.0
    revision_count: int = 0
    last_revision: datetime | None = None
    source: str | None = None
    applied: bool = False
    retention_score: float = 0.0

    def __post_init__(self) -> None:
        self._validate_confidence(self.confidence)

    @staticmethod
    def _validate_confidence(value: float) -> None:
        if not 0.0 <= value <= 100.0:
            raise DomainValidationError("Confidence must be between 0 and 100")

    def revise(self, at: datetime, confidence: float | None = None) -> None:
        self.revision_count += 1
        self.last_revision = at
        if confidence is not None:
            self._validate_confidence(confidence)
            self.confidence = confidence

    def mark_applied(self) -> None:
        self.applied = True

    def update_retention(self, retention_score: float) -> None:
        self.retention_score = retention_score
