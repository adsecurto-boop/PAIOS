"""PersistenceSync — event-driven write-back (approved ruling G2).

Subscribes to the announcement events and persists changed aggregates via
repository interfaces. Payload conventions (established in the approved
Milestone 4 design):

- EventStateChanged:  {"event": Event, "operation": "save"|"update"}
- ContextChanged:     {"context_window": ContextWindow,
                       "operation": "save"|"update"}
- PlanUpdated:        {"recommendations_updated": tuple[Recommendation,...],
                       "event_disturbers_updated": tuple[EventDisturber,...]}

PersistenceSync never transitions anything, never publishes, and contains
no decisions: it writes exactly what was announced.
"""

from paios.runtime.kernel import RepositoryProvider, RuntimeKernel
from paios.runtime.system_events import SystemEvent, SystemEventType


class PersistenceSync:
    def __init__(
        self, kernel: RuntimeKernel, repositories: RepositoryProvider
    ) -> None:
        self._kernel = kernel
        self._repositories = repositories
        self._attached = False

    def attach(self) -> None:
        if self._attached:
            return
        bus = self._kernel.event_bus
        bus.subscribe(SystemEventType.EVENT_STATE_CHANGED, self._on_event)
        bus.subscribe(SystemEventType.CONTEXT_CHANGED, self._on_context_window)
        bus.subscribe(SystemEventType.PLAN_UPDATED, self._on_plan)
        self._attached = True

    def _on_event(self, system_event: SystemEvent) -> None:
        event = system_event.payload.get("event")
        if event is None:
            return
        if system_event.payload.get("operation") == "save":
            self._repositories.events().save(event)
        else:
            self._repositories.events().update(event)

    def _on_context_window(self, system_event: SystemEvent) -> None:
        window = system_event.payload.get("context_window")
        if window is None:
            return
        if system_event.payload.get("operation") == "save":
            self._repositories.context_windows().save(window)
        else:
            self._repositories.context_windows().update(window)

    def _on_plan(self, system_event: SystemEvent) -> None:
        for recommendation in system_event.payload.get(
            "recommendations_updated", ()
        ):
            self._repositories.recommendations().update(recommendation)
        for disturber in system_event.payload.get(
            "event_disturbers_updated", ()
        ):
            self._repositories.event_disturbers().update(disturber)
