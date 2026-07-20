"""Command routing: every command performs exactly one primary delegation
into the Application facade.

Identifier resolution (`accept 1` -> the first listed recommendation) uses
read-only facade queries — input validation, never a second action. The
processor holds no state of its own beyond the Application it delegates to.
"""

from paios.application.application import Application
from paios.domain.enums import DisturberSeverity, DisturberType
from paios.domain.value_objects.identifiers import (
    EventId,
    RecommendationId,
    UserId,
)
from paios.cli import formatter
from paios.cli.exceptions import CliError, CommandArgumentError
from paios.cli.parser import COMMAND_SPECS, ParsedCommand

#: Fallback user when the store holds no aggregates to derive one from.
DEFAULT_USER_ID = "user_001"

_DEBUG_TARGETS = ("runtime", "scheduler", "kernel", "bus")


class CommandProcessor:
    """Routes parsed commands to the Application. Zero logic, one
    delegation per command."""

    def __init__(self, application: Application) -> None:
        self._app = application

    # --- dispatch --------------------------------------------------------

    def execute(self, command: ParsedCommand) -> str:
        handler = getattr(self, "_cmd_" + command.name.replace("-", "_"), None)
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
