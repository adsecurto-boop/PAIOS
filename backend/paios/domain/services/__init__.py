"""Domain services: cross-aggregate invariant checks and the invariant catalog."""

from paios.domain.services.invariants import (
    DOMAIN_INVARIANTS,
    DomainInvariant,
    InvariantScope,
    ensure_at_most_one_running_user_event,
    ensure_single_active_context_window,
    ensure_unique_context_window_ownership,
    find_running_event,
)

__all__ = [
    "DOMAIN_INVARIANTS",
    "DomainInvariant",
    "InvariantScope",
    "ensure_at_most_one_running_user_event",
    "ensure_single_active_context_window",
    "ensure_unique_context_window_ownership",
    "find_running_event",
]
