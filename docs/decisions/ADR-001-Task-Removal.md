# ADR-001: Task Removal

## Status

Accepted

## Context

PAIOS was originally designed with a Task entity as an intermediate step between Recommendations and Events.

The flow was:
- Recommendation → Task → Event

This created unnecessary complexity and did not align with PAIOS's philosophy as a Personal AI Operating System rather than a task manager.

## Decision

Remove Task as a domain entity from PAIOS.

The new flow is:
- Recommendation → Scheduler → Scheduled Event → Completed Event

Events remain the single source of truth in the system.

## Consequences

### Positive
- Simplifies the domain model
- Aligns with PAIOS philosophy (not a task manager)
- Events become the single source of truth
- Reduces state management complexity
- Clearer separation between planning (Scheduler) and execution (Events)

### Negative
- Requires migration of any existing Task-based implementations
- May require updates to user-facing terminology
- Scheduler complexity increases to handle direct Event planning

## Related Decisions

- ADR-002: Scheduler

## References

- Domain Model v0.2
- PAIOS Architecture Update Request
