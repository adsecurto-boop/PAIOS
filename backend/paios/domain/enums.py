"""Domain enumerations.

Sources:
- Event lifecycle: DOMAIN_MODEL.md Principle 19, BUSINESS_RULES.md Event
  Lifecycle Rules, STATE_MACHINES.md section 1. Exactly these twelve states;
  "Running" is a runtime concept (Started or Resumed), never an Event state.
- Event outcome: STATE_MACHINES.md section 1, "Event outcome".
- Context Window lifecycle: DOMAIN_MODEL.md Principle 18, STATE_MACHINES.md
  section 3.
- Recommendation lifecycle: STATE_MACHINES.md section 6 (approved resolution:
  Generated, Pending, Accepted, Rejected, Expired, Consumed).
- Event Disturber: DOMAIN_MODEL.md entity fields, STATE_MACHINES.md section 5.
- Remaining enums: DOMAIN_MODEL.md suggested field lists.
"""

from enum import Enum, unique


@unique
class EventStatus(Enum):
    """The canonical twelve-state Event Lifecycle."""

    RECOMMENDED = "Recommended"
    SCHEDULED = "Scheduled"
    READY = "Ready"
    STARTED = "Started"
    PAUSED = "Paused"
    RESUMED = "Resumed"
    COMPLETED = "Completed"
    SKIPPED = "Skipped"
    CANCELLED = "Cancelled"
    INTERRUPTED = "Interrupted"
    OVERTAKEN = "Overtaken"
    ARCHIVED = "Archived"


#: The Running Event concept (GLOSSARY.md): an Event in Started or Resumed
#: state. Running is NOT a lifecycle state of its own.
RUNNING_STATES: frozenset[EventStatus] = frozenset(
    {EventStatus.STARTED, EventStatus.RESUMED}
)


@unique
class EventOutcomeType(Enum):
    """What actually happened — immutable evidence, independent of lifecycle."""

    COMPLETED = "Completed"
    PARTIAL = "Partial"
    FAILED = "Failed"
    ABANDONED = "Abandoned"


@unique
class ImpactType(Enum):
    """Impact classification of a single Event (DOMAIN_MODEL.md Principle 15)."""

    OPPORTUNITY = "Opportunity"
    NEUTRAL = "Neutral"
    DISTRACTION = "Distraction"


@unique
class ContextWindowState(Enum):
    """Context Lifecycle — Windows have a lifecycle; Context itself does not."""

    CREATED = "Created"
    ACTIVE = "Active"
    CHANGING = "Changing"
    EXPIRED = "Expired"
    ARCHIVED = "Archived"


@unique
class RecommendationStatus(Enum):
    """Recommendation lifecycle (STATE_MACHINES.md section 6)."""

    GENERATED = "Generated"
    PENDING = "Pending"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    EXPIRED = "Expired"
    CONSUMED = "Consumed"


@unique
class DisturberType(Enum):
    FRIEND = "Friend"
    WORK = "Work"
    HEALTH = "Health"
    ENVIRONMENT = "Environment"
    FAMILY = "Family"
    OTHER = "Other"


@unique
class DisturberSeverity(Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


@unique
class DisturberResolutionStatus(Enum):
    PENDING = "Pending"
    RESOLVED = "Resolved"


@unique
class DisturberState(Enum):
    """Event Disturber state machine (STATE_MACHINES.md section 5)."""

    DETECTED = "Detected"
    RECORDED = "Recorded"
    ANALYZED = "Analyzed"
    APPLIED = "Applied"
    RESOLVED = "Resolved"
    ARCHIVED = "Archived"


@unique
class ResourceType(Enum):
    TIME = "Time"
    MONEY = "Money"
    HEALTH = "Health"
    ENERGY = "Energy"
    KNOWLEDGE = "Knowledge"
    FOCUS = "Focus"
    STRESS = "Stress"
    CAREER = "Career"
    SPIRITUAL = "Spiritual"


@unique
class ProjectStatus(Enum):
    ACTIVE = "Active"
    COMPLETED = "Completed"
    PAUSED = "Paused"


@unique
class GoalStatus(Enum):
    ACTIVE = "Active"
    COMPLETED = "Completed"
    PAUSED = "Paused"


@unique
class PrincipleCategory(Enum):
    HEALTH = "Health"
    RESPONSIBILITY = "Responsibility"
    TRUTH = "Truth"
    RESOURCES = "Resources"
    LEARNING = "Learning"
    DETACHMENT = "Detachment"
