"""Domain Invariants: the complete catalog, plus domain-service checks.

Every invariant from BUSINESS_RULES.md - Domain Invariants is DEFINED here.
Enforcement is split by scope (approved clarification):

- ENTITY: enforced inside a single aggregate, live in Milestone 1.
- DOMAIN_SERVICE: cross-aggregate; checkable here when a caller supplies the
  aggregates, but continuous enforcement belongs to later layers.
- RUNTIME_KERNEL: system-wide runtime guarantees; enforcement arrives with
  the Runtime Kernel milestone. Defined now, enforced later.
"""

from dataclasses import dataclass
from enum import Enum, unique
from typing import Iterable

from paios.domain.entities.context_window import ContextWindow
from paios.domain.entities.event import Event
from paios.domain.enums import ContextWindowState
from paios.domain.errors import InvariantViolationError


@unique
class InvariantScope(Enum):
    ENTITY = "Entity"
    DOMAIN_SERVICE = "Domain Service"
    RUNTIME_KERNEL = "Runtime Kernel"


@dataclass(frozen=True, slots=True)
class DomainInvariant:
    name: str
    description: str
    scope: InvariantScope
    enforced_in_milestone_1: bool
    notes: str | None = None


#: The complete invariant catalog (BUSINESS_RULES.md - Domain Invariants).
DOMAIN_INVARIANTS: tuple[DomainInvariant, ...] = (
    DomainInvariant(
        name="single-active-context-window",
        description="Exactly one Active Context Window (per User) at any given time.",
        scope=InvariantScope.RUNTIME_KERNEL,
        enforced_in_milestone_1=False,
        notes=(
            "Checkable now via ensure_single_active_context_window; continuous "
            "enforcement (auto-closing the previous Active window) is Runtime "
            "Kernel behavior."
        ),
    ),
    DomainInvariant(
        name="single-running-event",
        description="Exactly one Running Event (per User) at any given time.",
        scope=InvariantScope.RUNTIME_KERNEL,
        enforced_in_milestone_1=False,
        notes=(
            "NOT weakened (approved Resolution 3): exactly one logical Running "
            "Event always exists. When no user Event is running, the Runtime "
            "Kernel owns a System Idle Event (booting, waiting, sleeping, "
            "between Events) — a Runtime-layer concept, deliberately absent "
            "from the Domain layer. The domain can therefore verify only that "
            "at most one USER Event is running; the Kernel completes the "
            "exactly-one guarantee in a later milestone."
        ),
    ),
    DomainInvariant(
        name="completed-events-immutable",
        description="Completed Events are immutable.",
        scope=InvariantScope.ENTITY,
        enforced_in_milestone_1=True,
        notes="Event freezes its historical facts in post-execution states.",
    ),
    DomainInvariant(
        name="recommendations-never-modify-events",
        description="Recommendations never modify Events.",
        scope=InvariantScope.ENTITY,
        enforced_in_milestone_1=True,
        notes="Structural: Recommendation holds no Event reference at all.",
    ),
    DomainInvariant(
        name="resources-cannot-become-invalid",
        description=(
            "Resources cannot become invalid (e.g., negative where a negative "
            "value is not meaningful)."
        ),
        scope=InvariantScope.ENTITY,
        enforced_in_milestone_1=True,
        notes="Resource.consume rejects invalid results unless negative_allowed.",
    ),
    DomainInvariant(
        name="reflection-requires-event",
        description="A Reflection requires an Event — it cannot exist independently.",
        scope=InvariantScope.ENTITY,
        enforced_in_milestone_1=True,
        notes="Structural: Reflection.event_id is a required constructor argument.",
    ),
    DomainInvariant(
        name="progress-belongs-to-one-project",
        description="Progress belongs to exactly one Project.",
        scope=InvariantScope.ENTITY,
        enforced_in_milestone_1=True,
        notes=(
            "Structural: Progress.project_id is required; Project.attach_progress "
            "rejects a second Progress."
        ),
    ),
    DomainInvariant(
        name="context-window-references-one-context",
        description="A Context Window references exactly one Context.",
        scope=InvariantScope.ENTITY,
        enforced_in_milestone_1=True,
        notes="Structural: ContextWindow.context_id is a required single reference.",
    ),
    DomainInvariant(
        name="scheduler-never-edits-history",
        description="The Scheduler never edits History.",
        scope=InvariantScope.RUNTIME_KERNEL,
        enforced_in_milestone_1=False,
        notes=(
            "The domain contributes: post-execution Events reject fact mutation "
            "and terminal states reject reopening. Full enforcement is a "
            "Scheduler/Kernel obligation in later milestones."
        ),
    ),
    DomainInvariant(
        name="event-ids-immutable",
        description="Event IDs are immutable once assigned.",
        scope=InvariantScope.ENTITY,
        enforced_in_milestone_1=True,
        notes="Event.__setattr__ rejects any reassignment of event_id.",
    ),
    DomainInvariant(
        name="one-scheduler-per-user",
        description="Only one Scheduler exists per User.",
        scope=InvariantScope.RUNTIME_KERNEL,
        enforced_in_milestone_1=False,
        notes="The Scheduler is not a domain entity; enforced when it exists.",
    ),
    DomainInvariant(
        name="event-owns-one-context-window",
        description="Every Event owns exactly one Context Window.",
        scope=InvariantScope.DOMAIN_SERVICE,
        enforced_in_milestone_1=True,
        notes=(
            "Structural per Event (required single context_window_id); "
            "cross-aggregate uniqueness via ensure_unique_context_window_ownership."
        ),
    ),
    DomainInvariant(
        name="disturber-never-references-event-mutable-fields",
        description=(
            "An Event Disturber never has a direct foreign key to an Event's "
            "mutable fields — only to a resulting Context Window transition."
        ),
        scope=InvariantScope.ENTITY,
        enforced_in_milestone_1=True,
        notes=(
            "Structural: EventDisturber carries only a resulting Context Window "
            "reference and an evidential tuple of affected Event IDs."
        ),
    ),
    DomainInvariant(
        name="principles-never-altered-by-decision-engine",
        description=(
            "A Principle, once created, is never deleted or altered by the "
            "Decision Engine."
        ),
        scope=InvariantScope.ENTITY,
        enforced_in_milestone_1=True,
        notes=(
            "Structural: Principle is a frozen value; a review produces a new "
            "value via a deliberate User action."
        ),
    ),
)


# --- Cross-aggregate domain-service checks -------------------------------


def ensure_single_active_context_window(
    windows: Iterable[ContextWindow],
) -> ContextWindow | None:
    """Verify at most one Active Context Window among one User's windows.

    Returns the Active window, or None when none is Active (e.g. before the
    Runtime Kernel has activated one). Raises InvariantViolationError when
    more than one window is Active simultaneously.
    """
    active = [
        window
        for window in windows
        if window.current_state is ContextWindowState.ACTIVE
    ]
    if len(active) > 1:
        ids = ", ".join(str(window.window_id) for window in active)
        raise InvariantViolationError(
            f"Domain Invariant violated: {len(active)} Context Windows are "
            f"Active simultaneously ({ids}); exactly one is allowed"
        )
    return active[0] if active else None


def find_running_event(events: Iterable[Event]) -> Event | None:
    """Return the single running user Event (Started or Resumed), if any."""
    return ensure_at_most_one_running_user_event(events)


def ensure_at_most_one_running_user_event(
    events: Iterable[Event],
) -> Event | None:
    """Verify at most one of one User's Events is running.

    The full invariant is EXACTLY one logical Running Event per User
    (approved Resolution 3 — not weakened). The domain layer can only see
    user Events; when this returns None, the Runtime Kernel's System Idle
    Event (a Runtime-layer concept, later milestone) is the running
    execution context that keeps the invariant satisfied.
    """
    running = [event for event in events if event.is_running]
    if len(running) > 1:
        ids = ", ".join(str(event.event_id) for event in running)
        raise InvariantViolationError(
            f"Domain Invariant violated: {len(running)} Events are running "
            f"simultaneously ({ids}); exactly one Running Event is allowed"
        )
    return running[0] if running else None


def ensure_unique_context_window_ownership(events: Iterable[Event]) -> None:
    """Verify no two Events claim the same Context Window.

    Each Event structurally owns exactly one Context Window; this check adds
    the cross-aggregate half: a Context Window is owned by exactly one Event.
    """
    seen: dict[object, Event] = {}
    for event in events:
        owner = seen.get(event.context_window_id)
        if owner is not None and owner is not event:
            raise InvariantViolationError(
                f"Domain Invariant violated: Context Window "
                f"{event.context_window_id} is claimed by both Event "
                f"{owner.event_id} and Event {event.event_id}"
            )
        seen[event.context_window_id] = event
