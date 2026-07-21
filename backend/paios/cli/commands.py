"""Command routing: every command performs exactly one primary delegation
into the Application facade.

Identifier resolution (`accept 1` -> the first listed recommendation) uses
read-only facade queries — input validation, never a second action. The
processor holds no state of its own beyond the Application it delegates to.
"""

from paios.application.application import Application
from paios.domain.enums import (
    DisturberSeverity,
    DisturberType,
    PrincipleCategory,
    ResourceType,
)
from paios.domain.value_objects.identifiers import (
    ContextId,
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
from paios.cli import formatter
from paios.cli.exceptions import CliError, CommandArgumentError
from paios.cli.parser import COMMAND_SPECS, ParsedCommand
from paios.dashboard import ALLOWED_INTERVALS, DashboardConfig


def build_dashboard_config(args) -> DashboardConfig:
    """CLI-side validation of the dashboard refresh argument."""
    if not args:
        return DashboardConfig()
    token = args[0]
    if not token.isdigit() or int(token) not in ALLOWED_INTERVALS:
        raise CommandArgumentError(
            "Refresh must be one of: "
            + ", ".join(str(i) for i in ALLOWED_INTERVALS)
            + " (0 renders one frame and exits)"
        )
    return DashboardConfig(refresh_seconds=int(token))

#: Fallback user when the store holds no aggregates to derive one from.
DEFAULT_USER_ID = "user_001"

_DEBUG_TARGETS = ("runtime", "scheduler", "kernel", "bus")


class CommandProcessor:
    """Routes parsed commands to the Application. Zero logic, one
    delegation per command."""

    def __init__(self, application: Application) -> None:
        self._app = application

    @property
    def application(self) -> Application:
        """Read-only access for sibling presentation surfaces (the Shell
        hands the same Application to the Dashboard)."""
        return self._app

    # --- dispatch --------------------------------------------------------

    def execute(self, command: ParsedCommand) -> str:
        normalized = command.name.replace("-", "_").replace(" ", "_")
        handler = getattr(self, "_cmd_" + normalized, None)
        if handler is None:
            raise CliError(f"Command {command.name!r} has no handler")
        return handler(command.args)

    # --- system ----------------------------------------------------------

    def _cmd_start(self, args) -> str:
        self._app.start()
        return "PAIOS started."

    def _cmd_stop(self, args) -> str:
        self._app.stop()
        return "PAIOS stopped."

    def _cmd_status(self, args) -> str:
        return formatter.format_status(self._app.status())

    def _cmd_snapshot(self, args) -> str:
        return formatter.format_snapshot(self._app.snapshot())

    def _cmd_tick(self, args) -> str:
        return formatter.format_decision_result(self._app.tick())

    # --- recommendations -------------------------------------------------

    def _cmd_recommendations(self, args) -> str:
        return formatter.format_recommendations(
            self._app.active_recommendations()
        )

    def _cmd_accept(self, args) -> str:
        self._app.accept_recommendation(self._resolve_recommendation(args[0]))
        return "Recommendation accepted."

    def _cmd_reject(self, args) -> str:
        self._app.reject_recommendation(self._resolve_recommendation(args[0]))
        return "Recommendation rejected."

    # --- events ----------------------------------------------------------

    def _cmd_events(self, args) -> str:
        return formatter.format_events(self._events())

    def _cmd_event(self, args) -> str:
        event_id = self._resolve_event(args[0])
        event = next(
            e for e in self._events() if e.event_id == event_id
        )
        return formatter.format_event_detail(event)

    def _cmd_start_event(self, args) -> str:
        self._app.start_event(self._resolve_event(args[0]))
        return "Event started."

    def _cmd_pause_event(self, args) -> str:
        self._app.pause_event(self._resolve_event(args[0]))
        return "Event paused."

    def _cmd_resume_event(self, args) -> str:
        self._app.resume_event(self._resolve_event(args[0]))
        return "Event resumed."

    def _cmd_complete_event(self, args) -> str:
        actual_outcome = " ".join(args[1:]) or None
        self._app.complete_event(
            self._resolve_event(args[0]), actual_outcome=actual_outcome
        )
        return "Event completed."

    def _cmd_cancel_event(self, args) -> str:
        self._app.cancel_event(self._resolve_event(args[0]))
        return "Event cancelled."

    # --- context / projects / reflections --------------------------------

    def _cmd_context(self, args) -> str:
        return formatter.format_context(self._app.snapshot())

    def _cmd_projects(self, args) -> str:
        return formatter.format_projects(self._app.snapshot())

    def _cmd_reflect(self, args) -> str:
        # Read-only by design: reflection CAPTURE needs a Learning-layer
        # use case that does not exist yet (see CLI_REPORT.md).
        snapshot = self._app.snapshot()
        reflections = snapshot.reflections if snapshot is not None else ()
        return formatter.format_reflections(reflections)

    # --- disturbers ------------------------------------------------------

    def _cmd_disturb(self, args) -> str:
        disturber_type = self._parse_enum(DisturberType, args[0], "type")
        severity = self._parse_enum(DisturberSeverity, args[1], "severity")
        description = " ".join(args[2:])
        disturber = self._app.report_disturber(
            self._default_user(), disturber_type, description, severity
        )
        return formatter.format_disturber(disturber)

    # --- debug -----------------------------------------------------------

    def _cmd_debug(self, args) -> str:
        target = args[0]
        if target not in _DEBUG_TARGETS:
            raise CommandArgumentError(
                f"Unknown debug target {target!r}; "
                f"expected one of: {', '.join(_DEBUG_TARGETS)}"
            )
        if target == "runtime":
            return formatter.format_status(self._app.status())
        components = self._app.components
        if target == "scheduler":
            return formatter.format_debug_scheduler(components.scheduler)
        if target == "kernel":
            return formatter.format_debug_kernel(components.kernel)
        return formatter.format_debug_bus(components.kernel.event_bus)

    # --- help ------------------------------------------------------------

    def _cmd_help(self, args) -> str:
        return formatter.format_help(
            COMMAND_SPECS, args[0] if args else None
        )

    # --- domain operations: users ----------------------------------------

    def _cmd_user_add(self, args) -> str:
        user = self._app.add_user(" ".join(args))
        return f"User added: {user.name} ({user.user_id})"

    def _cmd_user_list(self, args) -> str:
        return formatter.format_users(self._app.list_users())

    def _cmd_user_show(self, args) -> str:
        return formatter.format_user_detail(
            self._app.get_user(self._resolve_user(args[0]))
        )

    # --- domain operations: goals ----------------------------------------

    def _cmd_goal_add(self, args) -> str:
        goal = self._app.add_goal(
            self._owner_user(), args[0], " ".join(args[1:])
        )
        return f"Goal added: {goal.name} ({goal.goal_id})"

    def _cmd_goal_list(self, args) -> str:
        return formatter.format_goals(self._app.list_goals())

    def _cmd_goal_show(self, args) -> str:
        return formatter.format_goal_detail(
            self._app.get_goal(self._resolve_goal(args[0]))
        )

    def _cmd_goal_accept(self, args) -> str:
        goal = self._app.accept_goal(self._resolve_goal(args[0]))
        return f"Goal accepted: {goal.name}"

    def _cmd_goal_complete(self, args) -> str:
        goal = self._app.complete_goal(self._resolve_goal(args[0]))
        return f"Goal completed: {goal.name}"

    def _cmd_goal_pause(self, args) -> str:
        goal = self._app.pause_goal(self._resolve_goal(args[0]))
        return f"Goal paused: {goal.name}"

    def _cmd_goal_resume(self, args) -> str:
        goal = self._app.resume_goal(self._resolve_goal(args[0]))
        return f"Goal resumed: {goal.name}"

    # --- domain operations: projects -------------------------------------

    def _cmd_project_add(self, args) -> str:
        project = self._app.add_project(
            self._owner_user(), args[0], " ".join(args[1:])
        )
        return f"Project added: {project.name} ({project.project_id})"

    def _cmd_project_list(self, args) -> str:
        return formatter.format_project_list(self._app.list_projects())

    def _cmd_project_show(self, args) -> str:
        project_id = self._resolve_project(args[0])
        return formatter.format_project_detail(
            self._app.get_project(project_id),
            self._app.get_project_progress(project_id),
        )

    def _cmd_project_progress(self, args) -> str:
        progress = self._app.update_project_progress(
            self._resolve_project(args[0]),
            self._parse_float(args[1], "percent"),
        )
        return f"Progress updated: {progress.completion_percentage:g}%"

    def _cmd_project_complete(self, args) -> str:
        project = self._app.complete_project(self._resolve_project(args[0]))
        return f"Project completed: {project.name}"

    def _cmd_project_pause(self, args) -> str:
        project = self._app.pause_project(self._resolve_project(args[0]))
        return f"Project paused: {project.name}"

    def _cmd_project_resume(self, args) -> str:
        project = self._app.resume_project(self._resolve_project(args[0]))
        return f"Project resumed: {project.name}"

    # --- domain operations: principles -----------------------------------

    def _cmd_principle_add(self, args) -> str:
        category = self._parse_enum(PrincipleCategory, args[1], "category")
        principle = self._app.add_principle(
            args[0], category, " ".join(args[2:])
        )
        return f"Principle added: {principle.name} ({principle.principle_id})"

    def _cmd_principle_list(self, args) -> str:
        return formatter.format_principles(self._app.list_principles())

    def _cmd_principle_show(self, args) -> str:
        return formatter.format_principle_detail(
            self._app.get_principle(self._resolve_principle(args[0]))
        )

    def _cmd_principle_review(self, args) -> str:
        principle = self._app.review_principle(self._resolve_principle(args[0]))
        return f"Principle reviewed: {principle.name}"

    # --- domain operations: resources ------------------------------------

    def _cmd_resource_add(self, args) -> str:
        resource = self._app.add_resource(
            self._owner_user(),
            self._parse_enum(ResourceType, args[0], "type"),
            self._parse_float(args[1], "value"),
            args[2],
        )
        return (
            f"Resource added: {resource.type.value} = "
            f"{resource.current_value:g} {resource.unit} "
            f"({resource.resource_id})"
        )

    def _cmd_resource_list(self, args) -> str:
        return formatter.format_resources(self._app.list_resources())

    def _cmd_resource_show(self, args) -> str:
        return formatter.format_resource_detail(
            self._app.get_resource(self._resolve_resource(args[0]))
        )

    def _cmd_resource_consume(self, args) -> str:
        resource = self._app.consume_resource(
            self._resolve_resource(args[0]),
            self._parse_float(args[1], "amount"),
        )
        return (
            f"Resource updated: {resource.type.value} = "
            f"{resource.current_value:g} {resource.unit}"
        )

    def _cmd_resource_produce(self, args) -> str:
        resource = self._app.produce_resource(
            self._resolve_resource(args[0]),
            self._parse_float(args[1], "amount"),
        )
        return (
            f"Resource updated: {resource.type.value} = "
            f"{resource.current_value:g} {resource.unit}"
        )

    # --- domain operations: contexts -------------------------------------

    _CONTEXT_FIELDS = (
        "location",
        "people",
        "emotion",
        "trigger",
        "reason",
        "environment",
        "notes",
    )

    def _cmd_context_add(self, args) -> str:
        fields = self._parse_fields(args[1:], self._CONTEXT_FIELDS)
        if "people" in fields:
            fields["people"] = tuple(
                person.strip()
                for person in fields["people"].split(",")
                if person.strip()
            )
        context = self._app.add_context(args[0], **fields)
        return f"Context added: {context.name} ({context.context_id})"

    def _cmd_context_list(self, args) -> str:
        return formatter.format_contexts(self._app.list_contexts())

    def _cmd_context_show(self, args) -> str:
        return formatter.format_context_detail(
            self._app.get_context(self._resolve_context(args[0]))
        )

    # --- domain operations: knowledge ------------------------------------

    _KNOWLEDGE_FIELDS = ("project", "difficulty", "confidence", "source")

    def _cmd_knowledge_add(self, args) -> str:
        fields = self._parse_fields(args[3:], self._KNOWLEDGE_FIELDS)
        if "project" in fields:
            fields["project_id"] = self._resolve_project(
                fields.pop("project")
            )
        if "confidence" in fields:
            fields["confidence"] = self._parse_float(
                fields["confidence"], "confidence"
            )
        knowledge = self._app.add_knowledge(
            self._owner_user(), args[0], args[1], args[2], **fields
        )
        return (
            f"Knowledge added: {knowledge.domain}/{knowledge.topic} — "
            f"{knowledge.concept} ({knowledge.knowledge_id})"
        )

    def _cmd_knowledge_list(self, args) -> str:
        return formatter.format_knowledge(self._app.list_knowledge())

    def _cmd_knowledge_show(self, args) -> str:
        return formatter.format_knowledge_detail(
            self._app.get_knowledge(self._resolve_knowledge(args[0]))
        )

    def _cmd_knowledge_revise(self, args) -> str:
        confidence = (
            self._parse_float(args[1], "confidence")
            if len(args) > 1
            else None
        )
        knowledge = self._app.revise_knowledge(
            self._resolve_knowledge(args[0]), confidence=confidence
        )
        return (
            f"Knowledge revised: {knowledge.concept} "
            f"(revision {knowledge.revision_count}, "
            f"confidence {knowledge.confidence:g})"
        )

    def _cmd_knowledge_apply(self, args) -> str:
        knowledge = self._app.apply_knowledge(self._resolve_knowledge(args[0]))
        return f"Knowledge marked applied: {knowledge.concept}"

    # --- domain operations: reflections ----------------------------------

    _REFLECTION_FIELDS = (
        "facts",
        "interpretation",
        "root_cause",
        "lesson_learned",
        "improvement",
        "confidence",
    )

    def _cmd_reflection_add(self, args) -> str:
        fields = self._parse_fields(args[1:], self._REFLECTION_FIELDS)
        if "confidence" in fields:
            fields["confidence"] = self._parse_float(
                fields["confidence"], "confidence"
            )
        reflection = self._app.add_reflection(
            self._resolve_event(args[0]), **fields
        )
        return f"Reflection added: {reflection.reflection_id}"

    def _cmd_reflection_list(self, args) -> str:
        return formatter.format_reflections(self._app.list_reflections())

    def _cmd_reflection_show(self, args) -> str:
        return formatter.format_reflection_detail(
            self._app.get_reflection(self._resolve_reflection(args[0]))
        )

    # --- domain operations: habits and insights (read-only) ---------------

    def _cmd_habit_list(self, args) -> str:
        return formatter.format_habits(self._app.list_habits())

    def _cmd_habit_show(self, args) -> str:
        return formatter.format_habit_detail(
            self._app.get_habit(self._resolve_habit(args[0]))
        )

    def _cmd_insight_list(self, args) -> str:
        return formatter.format_insights(self._app.list_insights())

    def _cmd_insight_show(self, args) -> str:
        return formatter.format_insight_detail(
            self._app.get_insight(self._resolve_insight(args[0]))
        )

    # --- events: archive (existing facade action, newly exposed) ----------

    def _cmd_archive_event(self, args) -> str:
        self._app.archive_event(self._resolve_event(args[0]))
        return "Event archived."

    # --- dashboard (stream-bound; runs from shell or `paios dashboard`) ---

    def _cmd_dashboard(self, args) -> str:
        # The dashboard writes frames directly to a terminal stream, which
        # the processor does not own; the Shell and `paios dashboard`
        # intercept this command and run the Dashboard themselves.
        raise CliError(
            "The dashboard runs from the interactive shell or "
            "`paios dashboard [seconds]`"
        )

    # --- resolution helpers (read-only queries; no second action) ---------

    def _resolve_recommendation(self, token: str) -> RecommendationId:
        active = self._app.active_recommendations()
        if token.isdigit():
            index = int(token)
            if not 1 <= index <= len(active):
                raise CommandArgumentError(
                    f"No recommendation number {index}; "
                    f"{len(active)} listed"
                )
            return active[index - 1].recommendation_id
        return RecommendationId(token)

    def _resolve_event(self, token: str) -> EventId:
        events = self._events()
        if token.isdigit():
            index = int(token)
            if not 1 <= index <= len(events):
                raise CommandArgumentError(
                    f"No event number {index}; {len(events)} listed"
                )
            return events[index - 1].event_id
        return EventId(token)

    def _events(self):
        snapshot = self._app.snapshot()
        return snapshot.events if snapshot is not None else ()

    @staticmethod
    def _resolve_entity(token: str, entities, id_attr: str, label: str):
        """Number -> position in the listed order; anything else -> raw id."""
        if token.isdigit():
            index = int(token)
            if not 1 <= index <= len(entities):
                raise CommandArgumentError(
                    f"No {label} number {index}; {len(entities)} listed"
                )
            return getattr(entities[index - 1], id_attr)
        return None

    def _resolve_user(self, token: str) -> UserId:
        resolved = self._resolve_entity(
            token, self._app.list_users(), "user_id", "user"
        )
        return resolved if resolved is not None else UserId(token)

    def _resolve_goal(self, token: str) -> GoalId:
        resolved = self._resolve_entity(
            token, self._app.list_goals(), "goal_id", "goal"
        )
        return resolved if resolved is not None else GoalId(token)

    def _resolve_project(self, token: str) -> ProjectId:
        resolved = self._resolve_entity(
            token, self._app.list_projects(), "project_id", "project"
        )
        return resolved if resolved is not None else ProjectId(token)

    def _resolve_principle(self, token: str) -> PrincipleId:
        resolved = self._resolve_entity(
            token, self._app.list_principles(), "principle_id", "principle"
        )
        return resolved if resolved is not None else PrincipleId(token)

    def _resolve_resource(self, token: str) -> ResourceId:
        resolved = self._resolve_entity(
            token, self._app.list_resources(), "resource_id", "resource"
        )
        return resolved if resolved is not None else ResourceId(token)

    def _resolve_context(self, token: str) -> ContextId:
        resolved = self._resolve_entity(
            token, self._app.list_contexts(), "context_id", "context"
        )
        return resolved if resolved is not None else ContextId(token)

    def _resolve_knowledge(self, token: str) -> KnowledgeId:
        resolved = self._resolve_entity(
            token, self._app.list_knowledge(), "knowledge_id", "knowledge item"
        )
        return resolved if resolved is not None else KnowledgeId(token)

    def _resolve_reflection(self, token: str) -> ReflectionId:
        resolved = self._resolve_entity(
            token, self._app.list_reflections(), "reflection_id", "reflection"
        )
        return resolved if resolved is not None else ReflectionId(token)

    def _resolve_habit(self, token: str) -> HabitId:
        resolved = self._resolve_entity(
            token, self._app.list_habits(), "habit_id", "habit"
        )
        return resolved if resolved is not None else HabitId(token)

    def _resolve_insight(self, token: str) -> InsightId:
        resolved = self._resolve_entity(
            token, self._app.list_insights(), "insight_id", "insight"
        )
        return resolved if resolved is not None else InsightId(token)

    def _owner_user(self) -> UserId:
        """The owning user for created aggregates: the first stored User,
        else the snapshot-derived default (input resolution, no action)."""
        users = self._app.list_users()
        if users:
            return users[0].user_id
        return self._default_user()

    @staticmethod
    def _parse_fields(tokens, allowed: tuple[str, ...]) -> dict:
        """Parse a `field=value` tail (CLI syntax, no meanings)."""
        fields: dict = {}
        for token in tokens:
            key, separator, value = token.partition("=")
            if not separator or not key or not value:
                raise CommandArgumentError(
                    f"Expected field=value, got {token!r}"
                )
            if key not in allowed:
                raise CommandArgumentError(
                    f"Unknown field {key!r}; expected one of: "
                    + ", ".join(allowed)
                )
            fields[key] = value
        return fields

    @staticmethod
    def _parse_float(token: str, label: str) -> float:
        try:
            return float(token)
        except ValueError:
            raise CommandArgumentError(
                f"Expected a number for {label}, got {token!r}"
            ) from None

    def _default_user(self) -> UserId:
        snapshot = self._app.snapshot()
        if snapshot is not None:
            user_ids = sorted(
                {
                    str(aggregate.user_id)
                    for collection in (
                        snapshot.events,
                        snapshot.projects,
                        snapshot.resources,
                        snapshot.goals,
                        snapshot.habits,
                    )
                    for aggregate in collection
                }
            )
            if user_ids:
                return UserId(user_ids[0])
        return UserId(DEFAULT_USER_ID)

    @staticmethod
    def _parse_enum(enum_cls, token: str, label: str):
        for member in enum_cls:
            if member.value.lower() == token.lower():
                return member
        valid = ", ".join(member.value for member in enum_cls)
        raise CommandArgumentError(
            f"Unknown {label} {token!r}; expected one of: {valid}"
        )
