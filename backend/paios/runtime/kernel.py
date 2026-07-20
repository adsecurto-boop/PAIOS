"""Runtime Kernel — the central orchestrator of PAIOS runtime.

Owns Runtime State, the runtime lifecycle, Runtime Snapshots, the System
Event Bus, the Clock abstraction, Runtime Status, the Service Registry,
invariant enforcement, and the Idle Execution Context — NOTHING ELSE.

The Kernel never schedules, never recommends, never reasons, never
persists, and never transitions a domain Event (the Scheduler is the sole
controller of Event transitions — BUSINESS_RULES.md). Repository access is
confined to the boot sequence and reaches only injected repository
INTERFACES (approved resolution C5): the Kernel never imports JsonStore,
JSON modules, or concrete repository classes.

Boot sequence (mission-specified):
    Boot -> load repositories -> restore aggregates -> validate structural
    integrity (inherent in Option B hydration; failures surface here) ->
    validate domain invariants -> establish the Execution Context (Idle
    when no user Event runs) -> initialize Runtime State -> create Runtime
    Snapshot -> Kernel Ready.
    (The snapshot is assembled after Runtime State exists because it is a
    view OF that state; both occur inside Boot, before Ready.)

Shutdown sequence:
    Running -> stop accepting work -> dispose runtime resources (services
    removed, bus notified) -> clear runtime state -> shutdown complete.
    History is untouched; Runtime State is ephemeral by design.
"""

from typing import Protocol

from paios.domain.errors import DomainError
from paios.domain.services.invariants import find_running_event
from paios.repositories.errors import RepositoryError
from paios.repositories.interfaces import (
    ContextRepository,
    ContextWindowRepository,
    EventDisturberRepository,
    EventRepository,
    GoalRepository,
    HabitRepository,
    InsightRepository,
    KnowledgeRepository,
    PrincipleRepository,
    ProgressRepository,
    ProjectRepository,
    RecommendationRepository,
    ReflectionRepository,
    ResourceRepository,
    UserRepository,
)
from paios.runtime.clock import Clock, SystemClock
from paios.runtime.event_bus import EventBus
from paios.runtime.exceptions import (
    BootError,
    KernelLifecycleError,
    RuntimeInvariantError,
    RuntimeKernelError,
)
from paios.runtime.lifecycle import (
    KERNEL_STATE_MACHINE,
    OPERATIONAL_STATES,
    KernelState,
)
from paios.runtime.runtime_snapshot import RuntimeSnapshot, SnapshotManager
from paios.runtime.runtime_state import (
    EventExecutionContext,
    ExecutionContext,
    IdleExecutionContext,
    IdleReason,
    RuntimeState,
)
from paios.runtime.runtime_status import RuntimeStatus
from paios.runtime.services import InvariantChecker, ServiceRegistry
from paios.runtime.system_events import SystemEvent, SystemEventType
from paios.domain.state_machines.machine import TransitionHistory

_ACTOR = "Runtime Kernel"

SERVICE_CLOCK = "clock"
SERVICE_EVENT_BUS = "event_bus"
SERVICE_SNAPSHOT_MANAGER = "snapshot_manager"
SERVICE_INVARIANT_CHECKER = "invariant_checker"


class RepositoryProvider(Protocol):
    """Structural contract for the injected repository access (C5).

    RepositoryFactory satisfies this protocol; the Kernel depends only on
    the abstraction and touches it exclusively during boot.
    """

    def users(self) -> UserRepository: ...
    def principles(self) -> PrincipleRepository: ...
    def contexts(self) -> ContextRepository: ...
    def context_windows(self) -> ContextWindowRepository: ...
    def events(self) -> EventRepository: ...
    def projects(self) -> ProjectRepository: ...
    def progress(self) -> ProgressRepository: ...
    def resources(self) -> ResourceRepository: ...
    def knowledge(self) -> KnowledgeRepository: ...
    def recommendations(self) -> RecommendationRepository: ...
    def event_disturbers(self) -> EventDisturberRepository: ...
    def reflections(self) -> ReflectionRepository: ...
    def insights(self) -> InsightRepository: ...
    def habits(self) -> HabitRepository: ...
    def goals(self) -> GoalRepository: ...


class RuntimeKernel:
    """Coordinates all runtime components and maintains system consistency."""

    def __init__(
        self,
        repositories: RepositoryProvider,
        clock: Clock | None = None,
    ) -> None:
        self._repositories = repositories
        self._clock: Clock = clock if clock is not None else SystemClock()
        self._bus = EventBus()
        self._registry = ServiceRegistry()
        self._invariant_checker = InvariantChecker()
        self._snapshot_manager = SnapshotManager(self._clock)
        self._lifecycle: TransitionHistory[KernelState] = TransitionHistory(
            KERNEL_STATE_MACHINE, KernelState.CREATED
        )
        self._state: RuntimeState | None = None
        self._booted_at = None

    # --- introspection ---------------------------------------------------

    @property
    def state(self) -> KernelState:
        return self._lifecycle.current_state

    @property
    def event_bus(self) -> EventBus:
        return self._bus

    @property
    def services(self) -> ServiceRegistry:
        return self._registry

    @property
    def clock(self) -> Clock:
        return self._clock

    @property
    def runtime_state(self) -> RuntimeState:
        self._require_operational()
        return self._state

    @property
    def latest_snapshot(self) -> RuntimeSnapshot | None:
        return self._snapshot_manager.latest

    def status(self) -> RuntimeStatus:
        state = self._state
        latest = self._snapshot_manager.latest
        return RuntimeStatus(
            state=self.state,
            is_operational=self.state in OPERATIONAL_STATES,
            booted_at=self._booted_at,
            execution_context=(
                state.execution_context if state is not None else None
            ),
            registered_services=self._registry.names(),
            aggregate_counts=(
                state.aggregate_counts() if state is not None else {}
            ),
            latest_snapshot_at=(latest.created_at if latest else None),
        )

    # --- lifecycle: boot -------------------------------------------------

    def boot(self) -> None:
        """Run the mission-specified boot sequence to Kernel Ready."""
        self._transition(KernelState.BOOTING)
        try:
            state = self._load_and_validate()
            self._state = state
            self._register_boot_services()
            self._snapshot_manager.create(state)
            self._publish(
                SystemEventType.SNAPSHOT_CREATED,
                {"created_at": self._snapshot_manager.latest.created_at.isoformat()},
            )
            self._transition(KernelState.READY)
            self._booted_at = self._clock.now()
            self._publish(
                SystemEventType.KERNEL_BOOTED,
                {"aggregates_loaded": sum(state.aggregate_counts().values())},
            )
            self._publish(SystemEventType.RUNTIME_READY, {})
        except (RepositoryError, DomainError, RuntimeKernelError) as exc:
            self._transition(KernelState.FAILED, reason=str(exc))
            self._state = None
            self._snapshot_manager.clear()
            for name in self._registry.names():
                self._registry.remove(name)
            raise BootError(f"Kernel boot failed: {exc}") from exc

    def _load_and_validate(self) -> RuntimeState:
        """Boot-only repository access: load, restore, validate, initialize.

        Structural integrity is guaranteed by Option B hydration inside the
        repositories (reconstitution validates every transition chain); a
        corrupted store surfaces here as a SerializationError.
        """
        provider = self._repositories
        users = tuple(provider.users().list())
        principles = tuple(provider.principles().list())
        contexts = tuple(provider.contexts().list())
        context_windows = tuple(provider.context_windows().list())
        events = tuple(provider.events().list())
        projects = tuple(provider.projects().list())
        progress = tuple(provider.progress().list())
        resources = tuple(provider.resources().list())
        knowledge = tuple(provider.knowledge().list())
        recommendations = tuple(provider.recommendations().list())
        event_disturbers = tuple(provider.event_disturbers().list())
        reflections = tuple(provider.reflections().list())
        insights = tuple(provider.insights().list())
        habits = tuple(provider.habits().list())
        goals = tuple(provider.goals().list())

        self._invariant_checker.enforce(events, context_windows)

        execution_context = self._initial_execution_context(events)
        return RuntimeState(
            current_time=self._clock.now(),
            execution_context=execution_context,
            users=users,
            principles=principles,
            contexts=contexts,
            context_windows=context_windows,
            events=events,
            projects=projects,
            progress=progress,
            resources=resources,
            knowledge=knowledge,
            recommendations=recommendations,
            event_disturbers=event_disturbers,
            reflections=reflections,
            insights=insights,
            habits=habits,
            goals=goals,
        )

    def _initial_execution_context(self, events) -> ExecutionContext:
        """Exactly one Execution Context, always (approved resolution C2)."""
        running = find_running_event(events)
        now = self._clock.now()
        if running is not None:
            return EventExecutionContext(
                since=now,
                event_id=running.event_id,
                context_window_id=running.context_window_id,
            )
        return IdleExecutionContext(since=now, reason=IdleReason.WAITING)

    def _register_boot_services(self) -> None:
        for name, service in (
            (SERVICE_CLOCK, self._clock),
            (SERVICE_EVENT_BUS, self._bus),
            (SERVICE_SNAPSHOT_MANAGER, self._snapshot_manager),
            (SERVICE_INVARIANT_CHECKER, self._invariant_checker),
        ):
            self._registry.register(name, service)
            self._publish(SystemEventType.SERVICE_REGISTERED, {"service": name})

    # --- lifecycle: run / pause / resume / shutdown ----------------------

    def start(self) -> None:
        """Ready -> Running: the kernel accepts work."""
        self._transition(KernelState.RUNNING)

    def pause(self) -> None:
        """Running -> Paused: stop accepting work; state is retained."""
        self._transition(KernelState.PAUSED)
        self._publish(SystemEventType.RUNTIME_PAUSED, {})

    def resume(self) -> None:
        """Paused -> Running: accept work again."""
        self._transition(KernelState.RUNNING)
        self._publish(SystemEventType.RUNTIME_RESUMED, {})

    def shutdown(self) -> None:
        """Stop accepting work, dispose resources, clear runtime state."""
        self._transition(KernelState.STOPPING)
        for name in self._registry.names():
            self._registry.remove(name)
            self._publish(SystemEventType.SERVICE_REMOVED, {"service": name})
        self._state = None
        self._snapshot_manager.clear()
        self._transition(KernelState.STOPPED)
        self._publish(SystemEventType.KERNEL_SHUTDOWN, {})

    # --- runtime operations ----------------------------------------------

    def set_execution_context(self, context: ExecutionContext) -> None:
        """Swap the one Execution Context (future Scheduler entry point).

        Requires the Running state — a paused or stopping kernel does not
        accept work. Publishes RunningEventChanged, RunningContextChanged
        when the owned Context Window changed, and SnapshotUpdated.
        """
        self._require(KernelState.RUNNING)
        if not isinstance(context, ExecutionContext):
            raise RuntimeInvariantError(
                "Exactly one Execution Context must exist; it cannot be "
                "replaced by a non-ExecutionContext value"
            )
        previous_window = self._state.running_context_window_id
        previous = self._state.replace_execution_context(context)
        self._publish(
            SystemEventType.RUNNING_EVENT_CHANGED,
            {
                "previous": type(previous).__name__,
                "current": type(context).__name__,
            },
        )
        current_window = self._state.running_context_window_id
        if current_window != previous_window:
            self._publish(
                SystemEventType.RUNNING_CONTEXT_CHANGED,
                {
                    "previous_window": (
                        str(previous_window) if previous_window else None
                    ),
                    "current_window": (
                        str(current_window) if current_window else None
                    ),
                },
            )
        self._refresh_snapshot()

    def refresh_snapshot(self) -> RuntimeSnapshot:
        """Rebuild the snapshot from in-memory Runtime State (never disk)."""
        self._require_operational()
        return self._refresh_snapshot()

    def _refresh_snapshot(self) -> RuntimeSnapshot:
        self._state.current_time = self._clock.now()
        snapshot = self._snapshot_manager.create(self._state)
        self._publish(
            SystemEventType.SNAPSHOT_UPDATED,
            {"created_at": snapshot.created_at.isoformat()},
        )
        return snapshot

    # --- Milestone 4 amendments (approved rulings G1/G6) ------------------
    # The Scheduler creates aggregates and REQUESTS runtime effects; the
    # Kernel admits them into Runtime State and EXECUTES Context Window
    # transitions with the documented actor "Runtime". These are the only
    # domain mutations the Kernel performs, per the G6 ruling.

    def admit_event(self, event, context_window) -> None:
        """Admit a Scheduler-materialized Event + owned Context Window.

        Publishes the persistence-convention events (operation "save") so
        the infrastructure PersistenceSync writes them back (G2)."""
        self._require(KernelState.RUNNING)
        self._state.admit_event(event, context_window)
        self._publish(
            SystemEventType.EVENT_STATE_CHANGED,
            {"event": event, "operation": "save"},
        )
        self._publish(
            SystemEventType.CONTEXT_CHANGED,
            {"context_window": context_window, "operation": "save"},
        )
        self._refresh_snapshot()

    def activate_context_window(
        self, window_id, at, reason: str | None = None
    ) -> None:
        """Execute Created -> Active (actor "Runtime"), auto-closing the
        previously Active window of the same User (BUSINESS_RULES.md)."""
        self._require(KernelState.RUNNING)
        window = self._find_window(window_id)
        owner = self._window_owner(window_id)
        for other in self._state.context_windows:
            if other.window_id == window_id or not other.is_active:
                continue
            if self._window_owner(other.window_id) == owner:
                other.expire(at, "Replaced by new Active Context Window")
                self._publish(
                    SystemEventType.CONTEXT_CHANGED,
                    {"context_window": other, "operation": "update"},
                )
        window.activate(at, reason)
        self._publish(
            SystemEventType.CONTEXT_CHANGED,
            {"context_window": window, "operation": "update"},
        )
        self._refresh_snapshot()

    def expire_context_window(
        self, window_id, at, reason: str | None = None
    ) -> None:
        """Execute Active/Changing -> Expired (actor "Runtime")."""
        self._require(KernelState.RUNNING)
        window = self._find_window(window_id)
        window.expire(at, reason)
        self._publish(
            SystemEventType.CONTEXT_CHANGED,
            {"context_window": window, "operation": "update"},
        )
        self._refresh_snapshot()

    def _find_window(self, window_id):
        for window in self._state.context_windows:
            if window.window_id == window_id:
                return window
        raise RuntimeKernelError(
            f"Context Window {window_id} is not in Runtime State"
        )

    def _window_owner(self, window_id):
        for event in self._state.events:
            if event.context_window_id == window_id:
                return event.user_id
        return None

    # --- internals -------------------------------------------------------

    def _transition(self, to_state: KernelState, reason: str | None = None) -> None:
        try:
            self._lifecycle.apply(to_state, self._clock.now(), _ACTOR, reason)
        except DomainError as exc:
            raise KernelLifecycleError(str(exc)) from exc

    def _require(self, expected: KernelState) -> None:
        if self.state is not expected:
            raise KernelLifecycleError(
                f"Operation requires kernel state {expected.value!r}; "
                f"current state is {self.state.value!r}"
            )

    def _require_operational(self) -> None:
        if self.state not in OPERATIONAL_STATES or self._state is None:
            raise KernelLifecycleError(
                f"Operation requires an operational kernel (Ready/Running/"
                f"Paused); current state is {self.state.value!r}"
            )

    def _publish(self, event_type: SystemEventType, payload: dict) -> None:
        self._bus.publish(
            SystemEvent(
                event_type=event_type,
                occurred_at=self._clock.now(),
                payload=payload,
            )
        )
