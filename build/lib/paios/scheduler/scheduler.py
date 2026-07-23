"""The Scheduler: sole controller of Event transitions, owner of the future.

Event-driven (G11): subscribes to exactly one bus topic —
SchedulerRecalculationRequested — and runs one deterministic cycle per
signal (G9). User actions arrive as explicit method calls (the user
triggers; the Scheduler is the transition actor, per STATE_MACHINES.md).

Separation of concerns:
- The Scheduler ORCHESTRATES: observes runtime state, applies Event and
  Recommendation transitions through the formal state machines, requests
  runtime effects from the Kernel (aggregate admission, Context Window
  transitions, Execution Context swaps — rulings G1/G6).
- The Planner COMPUTES plans (refinement 3) from immutable candidates.
- PersistenceSync (infrastructure) persists what the Scheduler announces
  on the bus (G2) — the Scheduler itself never touches persistence.

Deterministic rules (documented Domain-Policy-level choices):
- Every recalculation trigger causes a full deterministic cycle (G9).
- The Scheduler never rejects a Recommendation (G8) — rejection is the
  user's; infeasible consumption is DEFERRED and retried each cycle.
- Starting one Event while another runs pauses the running one first
  (the user's own choice, by definition of Paused).
- A Resumed Event that must pause or complete is first normalized
  Resumed -> Started ("execution continues" — the documented edge).
- Materializing a Recommendation binds the new Context Window to the
  currently active Context if any, else the first known Context; with no
  Context known, consumption stays deferred (the domain requires every
  Window to reference a Context, and Recommendations carry none — a gap
  recorded for the Decision Engine milestone).
- Skipped when Current Time passes the planned slot end unstarted;
  Ready when the planned start arrives.
- An Interrupted Event is Overtaken when a strictly higher-priority
  planned Event is due; otherwise it awaits Resume/Cancel.
"""

from contextlib import contextmanager
from datetime import datetime
from enum import Enum, unique
from typing import Iterator

from paios.domain.entities.context_window import ContextWindow
from paios.domain.entities.event import Event
from paios.domain.entities.event_disturber import EventDisturber
from paios.domain.entities.recommendation import Recommendation
from paios.domain.enums import (
    DisturberState,
    EventStatus,
    RecommendationStatus,
)
from paios.domain.value_objects.event_outcome import EventOutcome
from paios.domain.value_objects.identifiers import (
    ContextId,
    ContextWindowId,
    EventId,
    RecommendationId,
    UserId,
)
from paios.domain.value_objects.time import Duration
from paios.runtime.kernel import RuntimeKernel
from paios.runtime.lifecycle import KernelState
from paios.runtime.runtime_state import (
    EventExecutionContext,
    IdleExecutionContext,
    IdleReason,
)
from paios.runtime.system_events import SystemEvent, SystemEventType
from paios.scheduler.exceptions import SchedulerLifecycleError, UnknownWorkError
from paios.scheduler.lifecycle import SCHEDULER_STATE_MACHINE, SchedulerState
from paios.scheduler.plan import SchedulingPlan
from paios.scheduler.planner import DeterministicPlanner, PlanCandidate, Planner

SERVICE_SCHEDULER = "scheduler"

#: Event statuses the Planner may (re)slot into the future.
_PLANNABLE = frozenset(
    {
        EventStatus.SCHEDULED,
        EventStatus.READY,
        EventStatus.PAUSED,
        EventStatus.INTERRUPTED,
    }
)


@unique
class RecalculationReason(Enum):
    TIME_PROGRESSED = "TimeProgressed"
    CONTEXT_CHANGED = "ContextChanged"
    DISTURBANCE_DETECTED = "DisturbanceDetected"
    RECOMMENDATION_GENERATED = "RecommendationGenerated"
    RECOMMENDATION_ACCEPTED = "RecommendationAccepted"
    USER_ACTION = "UserAction"
    BOOT_ADOPTION = "BootAdoption"
    MANUAL = "Manual"


class Scheduler:
    """Orchestrates scheduling; computes nothing it can delegate."""

    def __init__(self, kernel: RuntimeKernel, planner: Planner | None = None):
        self._kernel = kernel
        self._planner: Planner = planner or DeterministicPlanner()
        self._state = SchedulerState.IDLE
        self._plan: SchedulingPlan | None = None
        self._candidates: dict[EventId, PlanCandidate] = {}
        self._attached = False
        self._busy = False
        self._pending: RecalculationReason | None = None

    # --- introspection ---------------------------------------------------

    @property
    def state(self) -> SchedulerState:
        return self._state

    @property
    def plan(self) -> SchedulingPlan | None:
        return self._plan

    # --- attachment (boot adoption) --------------------------------------

    def attach(self) -> None:
        """Register with the Kernel, subscribe to the single trigger topic,
        and adopt restored reality (expire stale Recommendations, plan
        existing Scheduled Events, monitor a restored running Event)."""
        if self._attached:
            raise SchedulerLifecycleError("Scheduler is already attached")
        self._kernel.services.register(SERVICE_SCHEDULER, self)
        self._kernel.event_bus.subscribe(
            SystemEventType.SCHEDULER_RECALCULATION_REQUESTED,
            self._on_recalculation_requested,
        )
        self._attached = True
        self._recalculate(
            self._kernel.clock.now(), RecalculationReason.BOOT_ADOPTION, {}
        )

    # --- the single subscription (G11) -----------------------------------

    def _on_recalculation_requested(self, system_event: SystemEvent) -> None:
        raw_reason = system_event.payload.get(
            "reason", RecalculationReason.MANUAL.value
        )
        try:
            reason = RecalculationReason(raw_reason)
        except ValueError:
            reason = RecalculationReason.MANUAL
        self._recalculate(
            system_event.occurred_at, reason, dict(system_event.payload)
        )

    def _recalculate(
        self, at: datetime, reason: RecalculationReason, payload: dict
    ) -> None:
        """Deterministic, re-entrancy-safe: signals arriving mid-cycle are
        coalesced into exactly one follow-up cycle."""
        if self._busy:
            self._pending = reason
            return
        self._busy = True
        try:
            self._run_cycle(at, reason, payload)
        finally:
            self._busy = False
            pending, self._pending = self._pending, None
        if pending is not None:
            self._recalculate(at, pending, {})

    @contextmanager
    def _action(self, at: datetime) -> Iterator[None]:
        """Guard a user action: recalculation signals raised while the
        action runs (e.g. the bridge reacting to ContextChanged) coalesce
        into exactly one deterministic follow-up cycle."""
        if self._busy:
            raise SchedulerLifecycleError(
                "Scheduler actions cannot re-enter a running cycle"
            )
        self._busy = True
        try:
            yield
        finally:
            self._busy = False
            pending, self._pending = self._pending, None
        if pending is not None:
            self._recalculate(at, pending, {})

    def _request_followup(self, reason: RecalculationReason) -> None:
        self._pending = reason

    # --- the scheduling cycle --------------------------------------------

    def _run_cycle(
        self, at: datetime, reason: RecalculationReason, payload: dict
    ) -> None:
        self._enter_cycle()
        changed_recommendations: list[Recommendation] = []
        changed_disturbers: list[EventDisturber] = []

        if reason is RecalculationReason.DISTURBANCE_DETECTED:
            self._apply_disturbance(at, payload, changed_disturbers)

        self._expire_stale_recommendations(at, changed_recommendations)
        self._consume_accepted_recommendations(at, changed_recommendations)
        self._advance_due_events(at)
        self._overtake_if_outranked(at)
        self._rebuild_plan(at)

        self._publish(
            SystemEventType.PLAN_UPDATED,
            {
                "reason": reason.value,
                "plan_entries": len(self._plan.entries) if self._plan else 0,
                "recommendations_updated": tuple(changed_recommendations),
                "event_disturbers_updated": tuple(changed_disturbers),
            },
        )
        self._exit_cycle()

    def _enter_cycle(self) -> None:
        if self._state is SchedulerState.IDLE:
            self._walk(
                SchedulerState.OBSERVING,
                SchedulerState.EVALUATING,
                SchedulerState.PLANNING,
                SchedulerState.SCHEDULING,
            )
        elif self._state is SchedulerState.MONITORING:
            self._walk(SchedulerState.RECALCULATING, SchedulerState.SCHEDULING)
        else:
            raise SchedulerLifecycleError(
                f"A cycle cannot begin from state {self._state.value!r}"
            )

    def _exit_cycle(self) -> None:
        self._walk(SchedulerState.MONITORING)
        nothing_running = self._running_event() is None
        if (self._plan is None or self._plan.is_empty) and nothing_running:
            self._walk(SchedulerState.IDLE)

    def _walk(self, *targets: SchedulerState) -> None:
        for target in targets:
            SCHEDULER_STATE_MACHINE.validate(self._state, target)
            self._state = target

    # --- cycle stages ----------------------------------------------------

    def _expire_stale_recommendations(
        self, at: datetime, changed: list[Recommendation]
    ) -> None:
        for recommendation in self._runtime().recommendations:
            if (
                recommendation.status is RecommendationStatus.PENDING
                and recommendation.is_expired(at)
            ):
                recommendation.expire(at, reason="Validity ended")
                changed.append(recommendation)

    def _consume_accepted_recommendations(
        self, at: datetime, changed: list[Recommendation]
    ) -> None:
        """Consume accepted Recommendations into Scheduled Events (G1).

        Requires a Running kernel (admission accepts work) and a bindable
        Context; otherwise the Recommendation stays deferred — never
        rejected (G8)."""
        if self._kernel.state is not KernelState.RUNNING:
            return
        for recommendation in tuple(self._runtime().recommendations):
            if recommendation.status is not RecommendationStatus.ACCEPTED:
                continue
            context_id = self._bindable_context_id()
            if context_id is None:
                continue  # deferred: no Context exists to bind a Window to
            self._materialize(recommendation, context_id, at)
            recommendation.consume(at, reason="Scheduled")
            changed.append(recommendation)

    def _materialize(
        self,
        recommendation: Recommendation,
        context_id: ContextId,
        at: datetime,
    ) -> Event:
        event_id = EventId.new()
        window_id = ContextWindowId.new()
        event = Event(
            event_id=event_id,
            user_id=recommendation.user_id,
            context_window_id=window_id,
            category="recommendation",
            description=recommendation.reason,
            project_id=recommendation.related_project_id,
            expected_outcome=recommendation.expected_benefit,
        )
        window = ContextWindow(
            window_id=window_id, context_id=context_id, event_id=event_id
        )
        event.transition_to(
            EventStatus.SCHEDULED, at, reason="Recommendation consumed"
        )
        self._kernel.admit_event(event, window)
        earliest = recommendation.suggested_timing or at
        self._candidates[event_id] = PlanCandidate(
            event_id=event_id,
            priority=(
                recommendation.priority
                if recommendation.priority is not None
                else 0.0
            ),
            earliest_start=max(earliest, at),
            recommendation_id=recommendation.recommendation_id,
        )
        return event

    def _advance_due_events(self, at: datetime) -> None:
        if self._plan is None:
            return
        for entry in self._plan.entries:
            event = self._find_event_or_none(entry.event_id)
            if event is None:
                continue
            # ADR-003: Scheduled and Ready share the Skipped exit when the
            # opportunity passes unstarted.
            if event.status in (EventStatus.SCHEDULED, EventStatus.READY):
                if at >= entry.planned_end:
                    event.transition_to(
                        EventStatus.SKIPPED, at, reason="Opportunity passed"
                    )
                    self._announce_event(event)
                    continue
            if event.status is EventStatus.SCHEDULED and at >= entry.planned_start:
                event.transition_to(
                    EventStatus.READY, at, reason="Planned time arrived"
                )
                self._announce_event(event)

    def _overtake_if_outranked(self, at: datetime) -> None:
        if self._plan is None:
            return
        interrupted = [
            event
            for event in self._runtime().events
            if event.status is EventStatus.INTERRUPTED
        ]
        for event in interrupted:
            own = self._plan.entry_for(event.event_id)
            own_priority = own.priority if own else 0.0
            outranked = any(
                entry.priority > own_priority
                and entry.planned_start <= at
                and entry.event_id != event.event_id
                for entry in self._plan.entries
            )
            if outranked:
                event.transition_to(
                    EventStatus.OVERTAKEN,
                    at,
                    reason="Higher-priority Event replaced continuation",
                )
                self._announce_event(event)
                self._candidates.pop(event.event_id, None)

    def _rebuild_plan(self, at: datetime) -> None:
        candidates: list[PlanCandidate] = []
        for event in self._runtime().events:
            if event.status not in _PLANNABLE:
                self._candidates.pop(event.event_id, None)
                continue
            candidate = self._candidates.get(event.event_id)
            if candidate is None:
                candidate = PlanCandidate(
                    event_id=event.event_id,
                    priority=0.0,
                    earliest_start=at,
                )
                self._candidates[event.event_id] = candidate
            candidates.append(candidate)
        self._plan = self._planner.plan(at, tuple(candidates))

    # --- disturbance handling (the mandatory chain, P24) ------------------

    def _apply_disturbance(
        self, at: datetime, payload: dict, changed: list[EventDisturber]
    ) -> None:
        """Disturber -> Context Window transition -> recalculation ->
        Event State Transition. Strictly in that order."""
        running = self._running_event()
        if running is not None:
            window = self._find_window_or_none(running.context_window_id)
            if (
                window is not None
                and window.is_active
                and self._kernel.state is KernelState.RUNNING
            ):
                self._kernel.expire_context_window(
                    window.window_id, at, reason="Disturbance"
                )
            running.transition_to(
                EventStatus.INTERRUPTED,
                at,
                reason="Disturbance forced recalculation",
            )
            self._announce_event(running)
            if self._kernel.state is KernelState.RUNNING:
                self._kernel.set_execution_context(
                    IdleExecutionContext(since=at, reason=IdleReason.WAITING)
                )
        disturber_id = payload.get("event_disturber_id")
        if disturber_id is not None:
            for disturber in self._runtime().event_disturbers:
                if (
                    str(disturber.event_disturber_id) == str(disturber_id)
                    and disturber.state is DisturberState.APPLIED
                ):
                    disturber.resolve(at)
                    changed.append(disturber)

    # --- user actions (the user triggers; the Scheduler is the actor) -----

    def accept_recommendation(
        self, recommendation_id: RecommendationId, at: datetime
    ) -> None:
        with self._action(at):
            recommendation = self._find_recommendation(recommendation_id)
            recommendation.accept(at, reason="User accepted")
            self._publish(
                SystemEventType.PLAN_UPDATED,
                {
                    "reason": RecalculationReason.RECOMMENDATION_ACCEPTED.value,
                    "plan_entries": (
                        len(self._plan.entries) if self._plan else 0
                    ),
                    "recommendations_updated": (recommendation,),
                    "event_disturbers_updated": (),
                },
            )
            self._request_followup(RecalculationReason.RECOMMENDATION_ACCEPTED)

    def user_rejected_recommendation(
        self,
        recommendation_id: RecommendationId,
        at: datetime,
        reason: str | None = None,
    ) -> None:
        """Applies the USER's rejection — the Scheduler never rejects (G8)."""
        recommendation = self._find_recommendation(recommendation_id)
        recommendation.reject(at, reason=reason or "User rejected")
        self._publish(
            SystemEventType.PLAN_UPDATED,
            {
                "reason": RecalculationReason.USER_ACTION.value,
                "plan_entries": len(self._plan.entries) if self._plan else 0,
                "recommendations_updated": (recommendation,),
                "event_disturbers_updated": (),
            },
        )

    def user_started(self, event_id: EventId, at: datetime) -> None:
        with self._action(at):
            event = self._find_event(event_id)
            self._pause_running_event(at)
            if event.status is EventStatus.SCHEDULED:
                event.transition_to(
                    EventStatus.READY, at, reason="Start requested"
                )
            event.transition_to(EventStatus.STARTED, at, reason="User began")
            self._kernel.activate_context_window(
                event.context_window_id, at, reason="Event started"
            )
            self._kernel.set_execution_context(
                EventExecutionContext(
                    since=at,
                    event_id=event.event_id,
                    context_window_id=event.context_window_id,
                )
            )
            self._announce_event(event)
            self._request_followup(RecalculationReason.USER_ACTION)

    def user_paused(self, event_id: EventId, at: datetime) -> None:
        with self._action(at):
            event = self._find_event(event_id)
            was_running_context = self._is_running_context(event)
            self._normalize_resumed(event, at)
            event.transition_to(EventStatus.PAUSED, at, reason="User paused")
            if was_running_context:
                self._kernel.set_execution_context(
                    IdleExecutionContext(since=at, reason=IdleReason.WAITING)
                )
            self._announce_event(event)
            self._request_followup(RecalculationReason.USER_ACTION)

    def user_resumed(self, event_id: EventId, at: datetime) -> None:
        with self._action(at):
            event = self._find_event(event_id)
            self._pause_running_event(at)
            event.transition_to(EventStatus.RESUMED, at, reason="User resumed")
            self._kernel.set_execution_context(
                EventExecutionContext(
                    since=at,
                    event_id=event.event_id,
                    context_window_id=event.context_window_id,
                )
            )
            self._announce_event(event)
            self._request_followup(RecalculationReason.USER_ACTION)

    def user_completed(
        self,
        event_id: EventId,
        at: datetime,
        outcome: EventOutcome | None = None,
        actual_outcome: str | None = None,
    ) -> None:
        """Completion with externally supplied Outcome evidence (G10)."""
        with self._action(at):
            event = self._find_event(event_id)
            was_running_context = self._is_running_context(event)
            if actual_outcome is not None:
                event.actual_outcome = actual_outcome
            if event.end_time is None:
                event.end_time = at
            if (
                event.duration is None
                and event.start_time is not None
                and event.end_time >= event.start_time
            ):
                event.duration = Duration.between(
                    event.start_time, event.end_time
                )
            event.transition_to(
                EventStatus.COMPLETED, at, reason="Completion confirmed"
            )
            if outcome is not None:
                event.record_outcome(outcome)
            window = self._find_window_or_none(event.context_window_id)
            if window is not None and window.is_active:
                self._kernel.expire_context_window(
                    window.window_id, at, reason="Event completed"
                )
            if was_running_context:
                self._kernel.set_execution_context(
                    IdleExecutionContext(
                        since=at, reason=IdleReason.BETWEEN_EVENTS
                    )
                )
            self._announce_event(event)
            self._request_followup(RecalculationReason.USER_ACTION)

    def user_cancelled(
        self, event_id: EventId, at: datetime, reason: str | None = None
    ) -> None:
        with self._action(at):
            event = self._find_event(event_id)
            event.transition_to(
                EventStatus.CANCELLED,
                at,
                reason=reason or "Deliberate abandonment",
            )
            self._announce_event(event)
            self._request_followup(RecalculationReason.USER_ACTION)

    def archive_event(self, event_id: EventId, at: datetime) -> None:
        event = self._find_event(event_id)
        event.transition_to(EventStatus.ARCHIVED, at, reason="Archival")
        self._announce_event(event)

    def report_spontaneous_action(
        self,
        user_id: UserId,
        category: str,
        description: str,
        at: datetime,
        context_id: ContextId | None = None,
    ) -> Event:
        """Capture a spontaneous user action as a real Event (G4).

        The Event enters through the front door of the lifecycle — the
        implicit legal chain Recommended -> Scheduled -> Ready -> Started,
        each step reason-tagged. Reality overrides planning: a running
        Event is paused first."""
        with self._action(at):
            bound_context = context_id or self._bindable_context_id()
            if bound_context is None:
                raise UnknownWorkError(
                    "A spontaneous Event needs a Context to bind its Context "
                    "Window to, and none is known"
                )
            self._pause_running_event(at)
            event_id = EventId.new()
            window_id = ContextWindowId.new()
            event = Event(
                event_id=event_id,
                user_id=user_id,
                context_window_id=window_id,
                category=category,
                description=description,
                start_time=at,
            )
            window = ContextWindow(
                window_id=window_id, context_id=bound_context, event_id=event_id
            )
            for status in (
                EventStatus.SCHEDULED,
                EventStatus.READY,
                EventStatus.STARTED,
            ):
                event.transition_to(status, at, reason="Spontaneous user action")
            self._kernel.admit_event(event, window)
            self._kernel.activate_context_window(
                window_id, at, reason="Spontaneous user action"
            )
            self._kernel.set_execution_context(
                EventExecutionContext(
                    since=at, event_id=event_id, context_window_id=window_id
                )
            )
            self._announce_event(event)
            self._request_followup(RecalculationReason.USER_ACTION)
        return event

    # --- helpers ----------------------------------------------------------

    def _runtime(self):
        return self._kernel.runtime_state

    def _running_event(self) -> Event | None:
        for event in self._runtime().events:
            if event.is_running:
                return event
        return None

    def _is_running_context(self, event: Event) -> bool:
        context = self._runtime().execution_context
        return (
            isinstance(context, EventExecutionContext)
            and context.event_id == event.event_id
        )

    def _pause_running_event(self, at: datetime) -> None:
        running = self._running_event()
        if running is None:
            return
        self._normalize_resumed(running, at)
        running.transition_to(
            EventStatus.PAUSED, at, reason="User began another action"
        )
        if self._kernel.state is KernelState.RUNNING:
            self._kernel.set_execution_context(
                IdleExecutionContext(since=at, reason=IdleReason.WAITING)
            )
        self._announce_event(running)

    @staticmethod
    def _normalize_resumed(event: Event, at: datetime) -> None:
        if event.status is EventStatus.RESUMED:
            event.transition_to(
                EventStatus.STARTED, at, reason="Execution continues"
            )

    def _bindable_context_id(self) -> ContextId | None:
        for window in self._runtime().context_windows:
            if window.is_active:
                return window.context_id
        contexts = sorted(
            self._runtime().contexts, key=lambda context: str(context.context_id)
        )
        return contexts[0].context_id if contexts else None

    def _find_event(self, event_id: EventId) -> Event:
        event = self._find_event_or_none(event_id)
        if event is None:
            raise UnknownWorkError(f"Event {event_id} is not in Runtime State")
        return event

    def _find_event_or_none(self, event_id: EventId) -> Event | None:
        for event in self._runtime().events:
            if event.event_id == event_id:
                return event
        return None

    def _find_window_or_none(
        self, window_id: ContextWindowId
    ) -> ContextWindow | None:
        for window in self._runtime().context_windows:
            if window.window_id == window_id:
                return window
        return None

    def _find_recommendation(
        self, recommendation_id: RecommendationId
    ) -> Recommendation:
        for recommendation in self._runtime().recommendations:
            if recommendation.recommendation_id == recommendation_id:
                return recommendation
        raise UnknownWorkError(
            f"Recommendation {recommendation_id} is not in Runtime State"
        )

    def _announce_event(self, event: Event) -> None:
        self._publish(
            SystemEventType.EVENT_STATE_CHANGED,
            {"event": event, "operation": "update"},
        )

    def _publish(self, event_type: SystemEventType, payload: dict) -> None:
        self._kernel.event_bus.publish(
            SystemEvent(
                event_type=event_type,
                occurred_at=self._kernel.clock.now(),
                payload=payload,
            )
        )
