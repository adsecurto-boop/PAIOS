"""Domain entities across the three architectural layers.

Layer 1 (Foundation): Principle. The Decision Engine is deliberately absent —
it is a stateless reasoning component with no data (DOMAIN_MODEL.md), so it
has no domain entity.

Layer 2 (Operational): User, Project, Event, Context, ContextWindow,
Resource, Knowledge, Recommendation, Progress, Reflection, EventDisturber.
The Scheduler is a runtime component (later milestone), not a domain entity.

Layer 3 (Emergent): Habit, Insight, Goal.
"""

from paios.domain.entities.base import Entity
from paios.domain.entities.context import Context
from paios.domain.entities.context_window import ContextWindow
from paios.domain.entities.event import Event, POST_EXECUTION_STATES
from paios.domain.entities.event_disturber import EventDisturber
from paios.domain.entities.goal import Goal
from paios.domain.entities.habit import Habit
from paios.domain.entities.insight import Insight
from paios.domain.entities.knowledge import Knowledge
from paios.domain.entities.principle import Principle
from paios.domain.entities.progress import Progress
from paios.domain.entities.project import Project
from paios.domain.entities.recommendation import Recommendation
from paios.domain.entities.reflection import Reflection
from paios.domain.entities.resource import Resource
from paios.domain.entities.user import User

__all__ = [
    "Context",
    "ContextWindow",
    "Entity",
    "Event",
    "EventDisturber",
    "Goal",
    "Habit",
    "Insight",
    "Knowledge",
    "POST_EXECUTION_STATES",
    "Principle",
    "Progress",
    "Project",
    "Recommendation",
    "Reflection",
    "Resource",
    "User",
]
