"""Service Registry and Invariant Checker.

Milestone 3 registers exactly four services: Clock, Event Bus, Snapshot
Manager, Invariant Checker. The Scheduler, Decision Engine, and Learning
Engine register in their own milestones — the registry exists so they plug
in without kernel rewrites.

The Invariant Checker enforces, at runtime scope, the Domain Invariants
that Milestone 1 defined but deferred to the Runtime Kernel
(BUSINESS_RULES.md - Domain Invariants; BEHAVIORAL_ARCHITECTURE.md
section 4: "Enforce invariants"). It contains no business logic of its
own — every check invokes the Milestone 1 domain services or is the
approved runtime invariant "exactly one Execution Context" (C2), which the
RuntimeState enforces structurally.
"""

from collections import defaultdict
from typing import Iterable

from paios.domain.entities.context_window import ContextWindow
from paios.domain.entities.event import Event
from paios.domain.errors import InvariantViolationError
from paios.domain.services.invariants import (
    ensure_at_most_one_running_user_event,
    ensure_single_active_context_window,
    ensure_unique_context_window_ownership,
)
from paios.domain.value_objects.identifiers import UserId
from paios.runtime.exceptions import RuntimeInvariantError, ServiceRegistryError


class ServiceRegistry:
    """Named registration and lookup of runtime services."""

    def __init__(self) -> None:
        self._services: dict[str, object] = {}

    def register(self, name: str, service: object) -> None:
        if name in self._services:
            raise ServiceRegistryError(
                f"Service {name!r} is already registered"
            )
        self._services[name] = service

    def get(self, name: str) -> object:
        if name not in self._services:
            raise ServiceRegistryError(f"Service {name!r} is not registered")
        return self._services[name]

    def remove(self, name: str) -> object:
        if name not in self._services:
            raise ServiceRegistryError(f"Service {name!r} is not registered")
        return self._services.pop(name)

    def contains(self, name: str) -> bool:
        return name in self._services

    def names(self) -> tuple[str, ...]:
        return tuple(self._services)


class InvariantChecker:
    """Runtime-scope enforcement of the deferred Domain Invariants."""

    def enforce(
        self,
        events: Iterable[Event],
        context_windows: Iterable[ContextWindow],
    ) -> None:
        """Verify the cross-aggregate invariants per User; raise on violation.

        - At most one running user Event per User — the "exactly one Running
          Event" guarantee is completed by the kernel's Execution Context
          (an IdleExecutionContext when no user Event runs).
        - Exactly-one-Active Context Window per User, enforced as at most
          one: only an EventExecutionContext owns a Context Window (C2), so
          an idle runtime legitimately has no Active window.
        - A Context Window is owned by exactly one Event.
        """
        events = tuple(events)
        context_windows = tuple(context_windows)
        try:
            ensure_unique_context_window_ownership(events)
            events_by_user: dict[UserId, list[Event]] = defaultdict(list)
            for event in events:
                events_by_user[event.user_id].append(event)
            for user_events in events_by_user.values():
                ensure_at_most_one_running_user_event(user_events)

            window_owner: dict[object, UserId] = {
                event.context_window_id: event.user_id for event in events
            }
            windows_by_user: dict[object, list[ContextWindow]] = defaultdict(list)
            for window in context_windows:
                owner = window_owner.get(window.window_id)
                windows_by_user[owner].append(window)
            for user_windows in windows_by_user.values():
                ensure_single_active_context_window(user_windows)
        except InvariantViolationError as exc:
            raise RuntimeInvariantError(str(exc)) from exc
