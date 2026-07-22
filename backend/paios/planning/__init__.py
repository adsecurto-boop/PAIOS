"""Planning module (Milestone 20): Inbox, Templates, Recurrences, Event
Metadata and user-intent processing.

Application-adjacent and NON-frozen: this package imports the Domain
only to construct Recommendations (the sanctioned external-intent
vehicle) and the Scheduler only for the Planner interface (the R3
extension seam). It never touches Runtime, Decision Engine or Learning
internals, holds no business rules about scheduling, and decides
nothing about time or priority — the Scheduler remains the single
scheduling authority.

Stores are synchronous write-through JSON files under
``<data_dir>/planning/`` (same durability posture as the repository
layer). Timestamps always arrive from the caller (the composed Clock
via the Application facade) — approved resolution C6 keeps
``SystemClock.now`` the codebase's sole OS-clock site.
"""

from paios.planning.classifier import ClassifiedLine, classify_lines
from paios.planning.intents import EventIntent, build_user_recommendation
from paios.planning.metadata_planner import MetadataPlanner
from paios.planning.service import PlanningService
from paios.planning.stores import (
    EventMetadataStore,
    InboxStore,
    RecurrenceStore,
    TemplateStore,
)

__all__ = [
    "ClassifiedLine",
    "classify_lines",
    "EventIntent",
    "build_user_recommendation",
    "MetadataPlanner",
    "PlanningService",
    "EventMetadataStore",
    "InboxStore",
    "RecurrenceStore",
    "TemplateStore",
]
