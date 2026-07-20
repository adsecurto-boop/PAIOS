"""The Application facade: one clean public interface, zero logic.

Every method delegates to the owning subsystem — the facade decides
nothing. It owns only the canonical startup/shutdown sequences and the
runtime loop pass.

Startup (deterministic; the mission's example order adjusted for one
documented reason — Scheduler boot adoption reads Runtime State, which
requires an operational kernel):

    build components -> PersistenceSync.attach -> RecalculationBridge.attach
    -> Kernel.boot() -> Kernel.start() -> Scheduler.attach() -> ready

Shutdown:

    facade closes -> Kernel.shutdown() (stop work, dispose services, clear
    ephemeral state) -> flush pending persistence (a documented no-op:
    PersistenceSync is synchronous write-through, nothing can be pending)
    -> stopped

The runtime loop pass (tick) is the composition of the documented loop
stages; its cadence stays caller-driven because the Timer Engine remains
an undesigned future component (DOMAIN_MODEL.md Future Questions).
"""

from datetime import datetime

from paios.decision_engine.engine import DecisionResult
from paios.domain.entities.event_disturber import EventDisturber
from paios.domain.entities.recommendation import Recommendation
from paios.domain.enums import DisturberSeverity, DisturberType
from paios.domain.value_objects.event_outcome import EventOutcome
from paios.domain.value_objects.identifiers import (
    ContextId,
    EventDisturberId,
    EventId,
    RecommendationId,
    UserId,
)
from paios.runtime.runtime_snapshot import RuntimeSnapshot
from paios.runtime.runtime_status import RuntimeStatus
from paios.runtime.system_events import SystemEvent, SystemEventType
from paios.application.bootstrap import Components, build_components
from paios.application.config import ApplicationConfig
from paios.application.exceptions import (
    ApplicationAlreadyStartedError,
    ApplicationNotStartedError,
)


class Application:
    """PAIOS as one runnable application. Composition and delegation only."""

    def __init__(self, config: ApplicationConfig | None = None) -> None:
        self._config = config if config is not None else ApplicationConfig()
        self._components: Components | None = None
        self._started = False

    # --- lifecycle -------------------------------------------------------

    @property
    def started(self) -> bool:
        return self._started

    def start(self) -> None:
        """The canonical startup sequence, deterministic end to end."""
        if self._started:
            raise ApplicationAlreadyStartedError(
                "The application is already started"
            )
        components = build_components(self._config)
        components.repositories.initialize()
        components.sync.attach()
        components.bridge.attach()
        components.kernel.boot()
        components.kernel.start()
        components.scheduler.attach()
        self._components = components
        self._started = True

    def stop(self) -> None:
        """The canonical shutdown sequence. History survives; ephemeral
        runtime state does not. Persistence needs no flush — every write
        already happened synchronously at announcement time."""
        components = self._require_started()
        components.kernel.shutdown()
        self._started = False

    # --- component access (composition root privilege; read-only intent) --

    @property
    def components(self) -> Components:
        return self._require_started()

    # --- queries ----------------------------------------------------------

    def status(self) -> RuntimeStatus:
        return self._require_started().kernel.status()

    def snapshot(self) -> RuntimeSnapshot | None:
        return self._require_started().kernel.latest_snapshot

    def active_recommendations(self) -> tuple[Recommendation, ...]:
        return self._require_started().kernel.runtime_state.active_recommendations

    def active_event_disturbers(self) -> tuple[EventDisturber, ...]:
        return (
            self._require_started().kernel.runtime_state.active_event_disturbers
        )

    # --- reasoning and the runtime loop -----------------------------------

    def evaluate(self) -> DecisionResult:
        """Pure reasoning over the latest snapshot; no side effects."""
        components = self._require_started()
        return components.engine.evaluate(components.kernel.latest_snapshot)

    def tick(self) -> DecisionResult:
        """One canonical runtime loop pass:

        Observe (TimeProgressed -> bridge -> Scheduler recalculation) ->
        Reason (Decision Engine over the fresh snapshot) -> Present
        (Generated -> Pending, the documented Runtime actor) -> Admit
        (Kernel broadcasts RecommendationGenerated; PersistenceSync saves;
        the bridge notifies the Scheduler)."""
        components = self._require_started()
        now = components.clock.now()
        components.kernel.event_bus.publish(
            SystemEvent(SystemEventType.TIME_PROGRESSED, now, {})
        )
        # Approved M9 correction: the Decision Engine must reason over a
        # CURRENT snapshot (DECISION_ENGINE.md section 3 - "Ensure all
        # inputs are current"); a stale snapshot time breaks deterministic
        # Recommendation identity under continuous operation.
        result = components.engine.evaluate(
            components.kernel.refresh_snapshot()
        )
        for reasoned in result.recommendations:
            recommendation = reasoned.recommendation
            recommendation.present(now)
            components.kernel.admit_recommendation(recommendation)
        return result

    def run(self, iterations: int) -> tuple[DecisionResult, ...]:
        """A bounded, deterministic runtime loop (no Timer Engine yet)."""
        return tuple(self.tick() for _ in range(iterations))

    # --- user actions (pure delegation to the Scheduler) -------------------

    def accept_recommendation(
        self, recommendation_id: RecommendationId, at: datetime | None = None
    ) -> None:
        components = self._require_started()
        components.scheduler.accept_recommendation(
            recommendation_id, self._moment(at)
        )

    def reject_recommendation(
        self,
        recommendation_id: RecommendationId,
        at: datetime | None = None,
        reason: str | None = None,
    ) -> None:
        components = self._require_started()
        components.scheduler.user_rejected_recommendation(
            recommendation_id, self._moment(at), reason=reason
        )

    def start_event(self, event_id: EventId, at: datetime | None = None) -> None:
        self._require_started().scheduler.user_started(
            event_id, self._moment(at)
        )

    def pause_event(self, event_id: EventId, at: datetime | None = None) -> None:
        self._require_started().scheduler.user_paused(event_id, self._moment(at))

    def resume_event(self, event_id: EventId, at: datetime | None = None) -> None:
        self._require_started().scheduler.user_resumed(
            event_id, self._moment(at)
        )

    def complete_event(
        self,
        event_id: EventId,
        at: datetime | None = None,
        outcome: EventOutcome | None = None,
        actual_outcome: str | None = None,
    ) -> None:
        self._require_started().scheduler.user_completed(
            event_id,
            self._moment(at),
            outcome=outcome,
            actual_outcome=actual_outcome,
        )

    def cancel_event(
        self,
        event_id: EventId,
        at: datetime | None = None,
        reason: str | None = None,
    ) -> None:
        self._require_started().scheduler.user_cancelled(
            event_id, self._moment(at), reason=reason
        )

    def archive_event(self, event_id: EventId, at: datetime | None = None) -> None:
        self._require_started().scheduler.archive_event(
            event_id, self._moment(at)
        )

    def report_spontaneous_action(
        self,
        user_id: UserId,
        category: str,
        description: str,
        at: datetime | None = None,
        context_id: ContextId | None = None,
    ):
        return self._require_started().scheduler.report_spontaneous_action(
            user_id, category, description, self._moment(at), context_id
        )

    def report_disturber(
        self,
        user_id: UserId,
        type: DisturberType,
        description: str,
        severity: DisturberSeverity,
        at: datetime | None = None,
        disturber_id: EventDisturberId | None = None,
    ) -> EventDisturber:
        """Capture an unexpected reality change (composition of documented
        steps, no decisions): create the Disturber, walk its Runtime-actor
        capture chain (Detected -> Recorded -> Analyzed -> Applied when an
        Active Context Window exists to transition — else it remains
        Analyzed evidence), then admit it. The Kernel broadcast triggers
        the Scheduler's mandatory chain; the Scheduler resolves it."""
        components = self._require_started()
        moment = self._moment(at)
        disturber = EventDisturber(
            event_disturber_id=(
                disturber_id if disturber_id is not None
                else EventDisturberId.new()
            ),
            user_id=user_id,
            type=type,
            description=description,
            severity=severity,
            occurred_at=moment,
        )
        disturber.record(moment)
        disturber.analyze(moment)
        active_window = components.kernel.runtime_state.running_context_window_id
        if active_window is not None:
            disturber.apply(moment, active_window)
        components.kernel.admit_event_disturber(disturber)
        return disturber

    # --- internals --------------------------------------------------------

    def _require_started(self) -> Components:
        if not self._started or self._components is None:
            raise ApplicationNotStartedError(
                "The application is not started; call start() first"
            )
        return self._components

    def _moment(self, at: datetime | None) -> datetime:
        if at is not None:
            return at
        return self._require_started().clock.now()
