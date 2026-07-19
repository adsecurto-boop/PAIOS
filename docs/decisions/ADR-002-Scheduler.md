# ADR-002: Scheduler

## Status

Accepted

## Context

PAIOS previously used a Timeline concept for planning future Events.

Timeline was insufficient for:
- Real-time recalculation based on changing conditions
- Handling Event Disturbers
- Dynamic scheduling based on Resources and Principles
- Time-based reasoning from Current Time

## Decision

Replace Timeline with Scheduler as the core planning component.

The Scheduler is responsible for:
- Planning future Events from the current moment
- Respecting Principles
- Respecting available Resources
- Respecting remaining time
- Consuming Recommendations
- Generating future Scheduled Events
- Recalculating based on Event Disturbers
- Never editing History

## Consequences

### Positive
- Enables real-time schedule recalculation
- Supports Event Disturbers as a defining concept
- Aligns with Time as a first-class domain concept
- Clearer separation between History and Planning
- Better support for dynamic resource management
- Enables Context Window-based scheduling

### Negative
- Increases complexity of planning logic
- Requires careful time tracking implementation
- May need Timer Engine for optimal operation
- Requires clear state machine for Event transitions

## Related Decisions

- ADR-001: Task Removal

## References

- Domain Model v0.2
- PAIOS Architecture Update Request
- Behavioral Architecture (future)
