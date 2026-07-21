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
from paios.domain.entities.context import Context
from paios.domain.entities.event_disturber import EventDisturber
from paios.domain.entities.goal import Goal
from paios.domain.entities.habit import Habit
from paios.domain.entities.insight import Insight
from paios.domain.entities.knowledge import Knowledge
from paios.domain.entities.principle import Principle
from paios.domain.entities.progress import Progress
from paios.domain.entities.project import Project
from paios.domain.entities.recommendation import Recommendation
from paios.domain.entities.reflection import Reflection
from paios.domain.entities.resource import Resource
from paios.domain.entities.user import User
from paios.domain.enums import (
    DisturberSeverity,
    DisturberType,
    PrincipleCategory,
    ResourceType,
)
from paios.domain.value_objects.event_outcome import EventOutcome
from paios.domain.value_objects.identifiers import (
    ContextId,
    EventDisturberId,
    EventId,
    GoalId,
    HabitId,
    InsightId,
    KnowledgeId,
    PrincipleId,
    ProjectId,
    RecommendationId,
    ReflectionId,
    ResourceId,
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

    def current_time(self) -> datetime:
        """The composed Clock's now — the one sanctioned time source
        (Milestone 11 additive query for read-only presentation)."""
        return self._require_started().clock.now()

    def scheduler_state(self):
        """The Scheduler's lifecycle state, read-only (Milestone 11
        additive query; pure delegation, no behavior)."""
        return self._require_started().scheduler.state

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

    # --- domain operations (Milestone 10; pure delegation) ----------------
    # Entity management goes application -> repositories.interfaces ->
    # domain, bypassing the Runtime by design: aggregates written here are
    # loaded into Runtime State at the next boot (the Kernel's repository
    # access is confined to its boot sequence — approved resolution C5).
    # All list/show queries below read the store, so they are always fresh.

    # users
    def add_user(self, name: str) -> User:
        return self._operations().add_user(name)

    def list_users(self) -> list[User]:
        return self._operations().list_users()

    def get_user(self, user_id: UserId) -> User:
        return self._operations().get_user(user_id)

    # goals
    def add_goal(
        self, user_id: UserId, name: str, description: str = ""
    ) -> Goal:
        return self._operations().add_goal(user_id, name, description)

    def list_goals(self) -> list[Goal]:
        return self._operations().list_goals()

    def get_goal(self, goal_id: GoalId) -> Goal:
        return self._operations().get_goal(goal_id)

    def accept_goal(self, goal_id: GoalId) -> Goal:
        return self._operations().accept_goal(goal_id)

    def complete_goal(self, goal_id: GoalId) -> Goal:
        return self._operations().complete_goal(goal_id)

    def pause_goal(self, goal_id: GoalId) -> Goal:
        return self._operations().pause_goal(goal_id)

    def resume_goal(self, goal_id: GoalId) -> Goal:
        return self._operations().resume_goal(goal_id)

    # projects
    def add_project(
        self, user_id: UserId, name: str, description: str = ""
    ) -> Project:
        return self._operations().add_project(user_id, name, description)

    def list_projects(self) -> list[Project]:
        return self._operations().list_projects()

    def get_project(self, project_id: ProjectId) -> Project:
        return self._operations().get_project(project_id)

    def get_project_progress(self, project_id: ProjectId) -> Progress | None:
        return self._operations().get_project_progress(project_id)

    def update_project_progress(
        self, project_id: ProjectId, completion_percentage: float
    ) -> Progress:
        return self._operations().update_project_progress(
            project_id, completion_percentage
        )

    def complete_project(self, project_id: ProjectId) -> Project:
        return self._operations().complete_project(project_id)

    def pause_project(self, project_id: ProjectId) -> Project:
        return self._operations().pause_project(project_id)

    def resume_project(self, project_id: ProjectId) -> Project:
        return self._operations().resume_project(project_id)

    # principles
    def add_principle(
        self, name: str, category: PrincipleCategory, description: str = ""
    ) -> Principle:
        return self._operations().add_principle(name, category, description)

    def list_principles(self) -> list[Principle]:
        return self._operations().list_principles()

    def get_principle(self, principle_id: PrincipleId) -> Principle:
        return self._operations().get_principle(principle_id)

    def review_principle(self, principle_id: PrincipleId) -> Principle:
        return self._operations().review_principle(principle_id)

    # resources
    def add_resource(
        self,
        user_id: UserId,
        type: ResourceType,
        current_value: float,
        unit: str,
        negative_allowed: bool = False,
    ) -> Resource:
        return self._operations().add_resource(
            user_id, type, current_value, unit, negative_allowed
        )

    def list_resources(self) -> list[Resource]:
        return self._operations().list_resources()

    def get_resource(self, resource_id: ResourceId) -> Resource:
        return self._operations().get_resource(resource_id)

    def consume_resource(
        self, resource_id: ResourceId, amount: float
    ) -> Resource:
        return self._operations().consume_resource(resource_id, amount)

    def produce_resource(
        self, resource_id: ResourceId, amount: float
    ) -> Resource:
        return self._operations().produce_resource(resource_id, amount)

    # contexts
    def add_context(
        self,
        name: str,
        location: str | None = None,
        people: tuple[str, ...] = (),
        emotion: str | None = None,
        trigger: str | None = None,
        reason: str | None = None,
        environment: str | None = None,
        notes: str | None = None,
    ) -> Context:
        return self._operations().add_context(
            name,
            location=location,
            people=people,
            emotion=emotion,
            trigger=trigger,
            reason=reason,
            environment=environment,
            notes=notes,
        )

    def list_contexts(self) -> list[Context]:
        return self._operations().list_contexts()

    def get_context(self, context_id: ContextId) -> Context:
        return self._operations().get_context(context_id)

    # knowledge
    def add_knowledge(
        self,
        user_id: UserId,
        domain: str,
        topic: str,
        concept: str,
        project_id: ProjectId | None = None,
        difficulty: str | None = None,
        confidence: float = 0.0,
        source: str | None = None,
    ) -> Knowledge:
        return self._operations().add_knowledge(
            user_id,
            domain,
            topic,
            concept,
            project_id=project_id,
            difficulty=difficulty,
            confidence=confidence,
            source=source,
        )

    def list_knowledge(self) -> list[Knowledge]:
        return self._operations().list_knowledge()

    def get_knowledge(self, knowledge_id: KnowledgeId) -> Knowledge:
        return self._operations().get_knowledge(knowledge_id)

    def revise_knowledge(
        self, knowledge_id: KnowledgeId, confidence: float | None = None
    ) -> Knowledge:
        return self._operations().revise_knowledge(
            knowledge_id, confidence=confidence
        )

    def apply_knowledge(self, knowledge_id: KnowledgeId) -> Knowledge:
        return self._operations().apply_knowledge(knowledge_id)

    # events (read-only listing; mutation stays with the Scheduler)
    def list_events(self) -> list:
        return self._operations().list_events()

    # reflections
    def add_reflection(
        self,
        event_id: EventId,
        facts: str | None = None,
        interpretation: str | None = None,
        root_cause: str | None = None,
        lesson_learned: str | None = None,
        improvement: str | None = None,
        confidence: float | None = None,
    ) -> Reflection:
        return self._operations().add_reflection(
            event_id,
            facts=facts,
            interpretation=interpretation,
            root_cause=root_cause,
            lesson_learned=lesson_learned,
            improvement=improvement,
            confidence=confidence,
        )

    def list_reflections(self) -> list[Reflection]:
        return self._operations().list_reflections()

    def get_reflection(self, reflection_id: ReflectionId) -> Reflection:
        return self._operations().get_reflection(reflection_id)

    # habits and insights (Learning Engine output; read-only)
    def list_habits(self) -> list[Habit]:
        return self._operations().list_habits()

    def get_habit(self, habit_id: HabitId) -> Habit:
        return self._operations().get_habit(habit_id)

    def list_insights(self) -> list[Insight]:
        return self._operations().list_insights()

    def get_insight(self, insight_id: InsightId) -> Insight:
        return self._operations().get_insight(insight_id)

    # --- internals --------------------------------------------------------

    def _operations(self):
        return self._require_started().operations

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
