"""The four formal domain state machines.

Transition sets are transcribed exactly from the formal transition tables in
STATE_MACHINES.md. Nothing is added and nothing is removed:

- Event (section 1): the twelve-state canonical lifecycle. Note that
  Overtaken has no outgoing transitions — per BUSINESS_RULES.md only
  Completed, Skipped, and Cancelled Events may transition to Archived.
- Context Window (section 3): Created/Active/Changing/Expired/Archived.
- Recommendation (section 6, plus approved Resolution 4): Generated ->
  Pending -> Accepted/Rejected/Expired; Accepted -> Consumed.
- Event Disturber (section 5): Detected -> Recorded -> Analyzed -> Applied ->
  Resolved -> Archived, strictly linear — Detected -> Applied is invalid.

STATE_MACHINES.md section 2 ("Scheduled Event Lifecycle") is deliberately NOT
modelled as a machine here: per approved Resolution 2 it is the Scheduler's
behavioral perspective of the one Event aggregate, not another aggregate.
"""

from paios.domain.enums import (
    ContextWindowState,
    DisturberState,
    EventStatus,
    RecommendationStatus,
)
from paios.domain.state_machines.machine import StateMachine

EVENT_STATE_MACHINE: StateMachine[EventStatus] = StateMachine(
    "Event Lifecycle",
    {
        EventStatus.RECOMMENDED: frozenset({EventStatus.SCHEDULED}),
        EventStatus.SCHEDULED: frozenset(
            {
                EventStatus.READY,
                EventStatus.SKIPPED,
                EventStatus.CANCELLED,
                EventStatus.OVERTAKEN,
            }
        ),
        # ADR-003: Ready shares every non-start exit of Scheduled — a Ready
        # Event is a Scheduled Event whose planned time has arrived.
        EventStatus.READY: frozenset(
            {
                EventStatus.STARTED,
                EventStatus.SKIPPED,
                EventStatus.CANCELLED,
                EventStatus.OVERTAKEN,
            }
        ),
        EventStatus.STARTED: frozenset(
            {
                EventStatus.PAUSED,
                EventStatus.INTERRUPTED,
                EventStatus.COMPLETED,
            }
        ),
        EventStatus.PAUSED: frozenset(
            {EventStatus.RESUMED, EventStatus.CANCELLED}
        ),
        EventStatus.RESUMED: frozenset(
            {EventStatus.STARTED, EventStatus.COMPLETED}
        ),
        EventStatus.INTERRUPTED: frozenset(
            {
                EventStatus.RESUMED,
                EventStatus.CANCELLED,
                EventStatus.OVERTAKEN,
            }
        ),
        EventStatus.COMPLETED: frozenset({EventStatus.ARCHIVED}),
        EventStatus.SKIPPED: frozenset({EventStatus.ARCHIVED}),
        EventStatus.CANCELLED: frozenset({EventStatus.ARCHIVED}),
        EventStatus.OVERTAKEN: frozenset(),
        EventStatus.ARCHIVED: frozenset(),
    },
)

CONTEXT_WINDOW_STATE_MACHINE: StateMachine[ContextWindowState] = StateMachine(
    "Context Window Lifecycle",
    {
        ContextWindowState.CREATED: frozenset({ContextWindowState.ACTIVE}),
        ContextWindowState.ACTIVE: frozenset(
            {ContextWindowState.CHANGING, ContextWindowState.EXPIRED}
        ),
        ContextWindowState.CHANGING: frozenset({ContextWindowState.EXPIRED}),
        ContextWindowState.EXPIRED: frozenset({ContextWindowState.ARCHIVED}),
        ContextWindowState.ARCHIVED: frozenset(),
    },
)

RECOMMENDATION_STATE_MACHINE: StateMachine[RecommendationStatus] = StateMachine(
    "Recommendation Lifecycle",
    {
        RecommendationStatus.GENERATED: frozenset({RecommendationStatus.PENDING}),
        RecommendationStatus.PENDING: frozenset(
            {
                RecommendationStatus.ACCEPTED,
                RecommendationStatus.REJECTED,
                RecommendationStatus.EXPIRED,
            }
        ),
        RecommendationStatus.ACCEPTED: frozenset({RecommendationStatus.CONSUMED}),
        RecommendationStatus.REJECTED: frozenset(),
        RecommendationStatus.EXPIRED: frozenset(),
        RecommendationStatus.CONSUMED: frozenset(),
    },
)

DISTURBER_STATE_MACHINE: StateMachine[DisturberState] = StateMachine(
    "Event Disturber Lifecycle",
    {
        DisturberState.DETECTED: frozenset({DisturberState.RECORDED}),
        DisturberState.RECORDED: frozenset({DisturberState.ANALYZED}),
        DisturberState.ANALYZED: frozenset({DisturberState.APPLIED}),
        DisturberState.APPLIED: frozenset({DisturberState.RESOLVED}),
        DisturberState.RESOLVED: frozenset({DisturberState.ARCHIVED}),
        DisturberState.ARCHIVED: frozenset(),
    },
)
