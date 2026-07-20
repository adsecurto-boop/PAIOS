"""Command parsing and syntax validation.

The parser knows names, arities, and usage strings — never meanings.
"""

from dataclasses import dataclass

from paios.cli.exceptions import CommandArgumentError, UnknownCommandError


@dataclass(frozen=True)
class CommandSpec:
    name: str
    usage: str
    description: str
    min_args: int = 0
    max_args: int | None = 0  # None = unbounded (free-text tail)


@dataclass(frozen=True)
class ParsedCommand:
    name: str
    args: tuple[str, ...] = ()


_SPECS = (
    CommandSpec("start", "start", "Start the application (boot PAIOS)"),
    CommandSpec("stop", "stop", "Stop the application"),
    CommandSpec("status", "status", "Show runtime status"),
    CommandSpec("snapshot", "snapshot", "Show the latest runtime snapshot"),
    CommandSpec("tick", "tick", "Run one runtime loop pass"),
    CommandSpec(
        "recommendations", "recommendations", "List active recommendations"
    ),
    CommandSpec("accept", "accept <ref>", "Accept a recommendation", 1, 1),
    CommandSpec("reject", "reject <ref>", "Reject a recommendation", 1, 1),
    CommandSpec("events", "events", "List events"),
    CommandSpec("event", "event <ref>", "Show one event in detail", 1, 1),
    CommandSpec("start-event", "start-event <ref>", "Start an event", 1, 1),
    CommandSpec("pause-event", "pause-event <ref>", "Pause an event", 1, 1),
    CommandSpec("resume-event", "resume-event <ref>", "Resume an event", 1, 1),
    CommandSpec(
        "complete-event",
        "complete-event <ref> [actual outcome...]",
        "Complete an event, optionally recording what actually happened",
        1,
        None,
    ),
    CommandSpec("cancel-event", "cancel-event <ref>", "Cancel an event", 1, 1),
    CommandSpec("context", "context", "Show contexts and the current situation"),
    CommandSpec("projects", "projects", "List projects and their progress"),
    CommandSpec("reflect", "reflect", "List reflections (read-only)"),
    CommandSpec(
        "disturb",
        "disturb <type> <severity> <description...>",
        "Report an unexpected disturbance",
        3,
        None,
    ),
    CommandSpec(
        "debug",
        "debug <runtime|scheduler|kernel|bus>",
        "Show internal diagnostics",
        1,
        1,
    ),
    CommandSpec("help", "help [command]", "Show help", 0, 1),
)

COMMAND_SPECS: dict[str, CommandSpec] = {spec.name: spec for spec in _SPECS}


def parse_line(line: str) -> ParsedCommand | None:
    """Parse one input line; returns None for blank input."""
    tokens = line.split()
    if not tokens:
        return None
    name, args = tokens[0], tuple(tokens[1:])
    spec = COMMAND_SPECS.get(name)
    if spec is None:
        raise UnknownCommandError(
            f"Unknown command: {name!r}. Type 'help' for the command list."
        )
    if len(args) < spec.min_args:
        raise CommandArgumentError(f"Usage: {spec.usage}")
    if spec.max_args is not None and len(args) > spec.max_args:
        raise CommandArgumentError(f"Usage: {spec.usage}")
    return ParsedCommand(name=name, args=args)
