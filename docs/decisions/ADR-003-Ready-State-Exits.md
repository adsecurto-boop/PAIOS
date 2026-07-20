# ADR-003: Ready-State Exits

## Status

Accepted

## Context

Scheduler implementation (Milestone 4) surfaced a dead-end in the formal
Event Lifecycle: `Ready` had exactly one exit — `Started`. A Ready Event
whose planned slot passed unstarted could be neither Skipped (only
`Scheduled → Skipped` existed) nor Cancelled (only Scheduled, Paused, or
Interrupted could cancel), leaving it trapped until the user started it.
This contradicted the intent of `Skipped` ("a Scheduled opportunity passed
without a start") and removed the user's freedom not to act — a freedom
the architecture guarantees everywhere else.

Additionally, the informal example lists in DOMAIN_MODEL.md (Principle 20)
and BUSINESS_RULES.md used the shorthand `Scheduled → Started`, which
contradicted the formal STATE_MACHINES.md path
`Scheduled → Ready → Started`.

## Decision

**Ready shares every non-start exit of Scheduled**, because a Ready Event
IS a Scheduled Event whose planned time has arrived:

- `Ready → Skipped` — the opportunity passed without a start.
- `Ready → Cancelled` — deliberate abandonment.
- `Ready → Overtaken` — a Principle-respecting higher-priority replacement.

The Scheduler remains the sole actor for all three, exactly as for their
Scheduled counterparts. Invalid transitions are unchanged: no terminal
state may return to Ready.

The informal example lists in DOMAIN_MODEL.md and BUSINESS_RULES.md are
aligned to the formal transition tables.

## Consequences

### Positive
- No lifecycle dead-ends: every non-terminal state has a time-driven or
  user-driven exit.
- `Skipped` semantics become uniform — an unstarted opportunity lapses the
  same way whether or not it was marked Ready first.
- The user's freedom not to start is preserved after readiness.
- The informal and formal documents now agree edge-for-edge.

### Negative
- Three new edges in the Event state machine (implementation, docs, and
  tests updated together in this revision).
- Historical data recorded before this revision cannot contain the new
  edges, so no migration is required.

## Architecture Consistency Statement

As of this revision the canonical architecture is declared **internally
consistent**: the four domain documents, STATE_MACHINES.md, and the
implementation agree edge-for-edge on all four state machines; the known
deviations of BEHAVIORAL_ARCHITECTURE.md §8 (extended Event states) and
STATE_MACHINES.md §2 (Scheduled-Event planning view) remain governed by the
approved Milestone 1 resolutions (canonical twelve-state lifecycle; one
Event aggregate) and CANONICAL_ORDER.md precedence. Verified by the full
test suite after regeneration.

## Related Decisions

- ADR-001: Task Removal
- ADR-002: Scheduler
- Approved Milestone 1 resolutions (canonical lifecycle; one Event aggregate)
- Milestone 4 rulings G1–G11

## References

- STATE_MACHINES.md section 1 (revision note)
- SCHEDULER_REPORT.md section 8 (the originating finding)
