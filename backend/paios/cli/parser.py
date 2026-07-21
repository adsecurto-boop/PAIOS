"""Command parsing and syntax validation.

The parser knows names, arities, and usage strings — never meanings.

Milestone 10 additions: command names may be two tokens (`goal add`) so
entity management reads noun-verb; arguments may be double-quoted so names
can contain spaces (`goal add "Learn Sanskrit"`). Both are purely
syntactic — the parser still knows nothing about meanings.
"""

import shlex
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
    CommandSpec(
        "dashboard",
        "dashboard [seconds]",
        "Live read-only dashboard; refresh 0(=once)/1/5/10s, Ctrl+C exits",
        0,
        1,
    ),
    # --- Milestone 10: Domain Operations (entity management) -------------
    CommandSpec("user add", "user add <name...>", "Create a user", 1, None),
    CommandSpec("user list", "user list", "List users"),
    CommandSpec("user show", "user show <ref>", "Show one user", 1, 1),
    CommandSpec(
        "goal add",
        'goal add <name> [description...]',
        "Create a goal (quote multi-word names)",
        1,
        None,
    ),
    CommandSpec("goal list", "goal list", "List goals"),
    CommandSpec("goal show", "goal show <ref>", "Show one goal", 1, 1),
    CommandSpec(
        "goal accept", "goal accept <ref>", "Accept a suggested goal", 1, 1
    ),
    CommandSpec(
        "goal complete", "goal complete <ref>", "Mark a goal Completed", 1, 1
    ),
    CommandSpec("goal pause", "goal pause <ref>", "Mark a goal Paused", 1, 1),
    CommandSpec(
        "goal resume", "goal resume <ref>", "Mark a goal Active again", 1, 1
    ),
    CommandSpec(
        "project add",
        'project add <name> [description...]',
        "Create a project (with its Progress)",
        1,
        None,
    ),
    CommandSpec("project list", "project list", "List projects"),
    CommandSpec(
        "project show", "project show <ref>", "Show one project", 1, 1
    ),
    CommandSpec(
        "project progress",
        "project progress <ref> <percent>",
        "Update a project's completion percentage",
        2,
        2,
    ),
    CommandSpec(
        "project complete",
        "project complete <ref>",
        "Mark a project Completed",
        1,
        1,
    ),
    CommandSpec(
        "project pause", "project pause <ref>", "Mark a project Paused", 1, 1
    ),
    CommandSpec(
        "project resume",
        "project resume <ref>",
        "Mark a project Active again",
        1,
        1,
    ),
    CommandSpec(
        "principle add",
        'principle add <name> <category> [description...]',
        "Create a principle",
        2,
        None,
    ),
    CommandSpec("principle list", "principle list", "List principles"),
    CommandSpec(
        "principle show", "principle show <ref>", "Show one principle", 1, 1
    ),
    CommandSpec(
        "principle review",
        "principle review <ref>",
        "Record a deliberate review of a principle",
        1,
        1,
    ),
    CommandSpec(
        "resource add",
        "resource add <type> <value> <unit>",
        "Create a resource",
        3,
        3,
    ),
    CommandSpec("resource list", "resource list", "List resources"),
    CommandSpec(
        "resource show", "resource show <ref>", "Show one resource", 1, 1
    ),
    CommandSpec(
        "resource consume",
        "resource consume <ref> <amount>",
        "Consume from a resource",
        2,
        2,
    ),
    CommandSpec(
        "resource produce",
        "resource produce <ref> <amount>",
        "Produce into a resource",
        2,
        2,
    ),
    CommandSpec(
        "context add",
        'context add <name> [field=value...]',
        "Create a context (fields: location, people, emotion, trigger, "
        "reason, environment, notes)",
        1,
        None,
    ),
    CommandSpec("context list", "context list", "List contexts"),
    CommandSpec(
        "context show", "context show <ref>", "Show one context", 1, 1
    ),
    CommandSpec(
        "knowledge add",
        'knowledge add <domain> <topic> <concept> [field=value...]',
        "Create a knowledge item (fields: project, difficulty, confidence, "
        "source)",
        3,
        None,
    ),
    CommandSpec("knowledge list", "knowledge list", "List knowledge items"),
    CommandSpec(
        "knowledge show",
        "knowledge show <ref>",
        "Show one knowledge item",
        1,
        1,
    ),
    CommandSpec(
        "knowledge revise",
        "knowledge revise <ref> [confidence]",
        "Record a revision (optionally with new confidence)",
        1,
        2,
    ),
    CommandSpec(
        "knowledge apply",
        "knowledge apply <ref>",
        "Mark a knowledge item as applied",
        1,
        1,
    ),
    CommandSpec(
        "reflection add",
        'reflection add <event-ref> [field=value...]',
        "Reflect on a completed event (fields: facts, interpretation, "
        "root_cause, lesson_learned, improvement, confidence)",
        1,
        None,
    ),
    CommandSpec("reflection list", "reflection list", "List reflections"),
    CommandSpec(
        "reflection show",
        "reflection show <ref>",
        "Show one reflection",
        1,
        1,
    ),
    CommandSpec("habit list", "habit list", "List habits (read-only)"),
    CommandSpec(
        "habit show", "habit show <ref>", "Show one habit (read-only)", 1, 1
    ),
    CommandSpec("insight list", "insight list", "List insights (read-only)"),
    CommandSpec(
        "insight show",
        "insight show <ref>",
        "Show one insight (read-only)",
        1,
        1,
    ),
    CommandSpec(
        "archive-event",
        "archive-event <ref>",
        "Archive a Completed/Skipped/Cancelled event",
        1,
        1,
    ),
)

COMMAND_SPECS: dict[str, CommandSpec] = {spec.name: spec for spec in _SPECS}


def parse_line(line: str) -> ParsedCommand | None:
    """Parse one input line; returns None for blank input.

    The longest matching command name wins: `goal add` is looked up as a
    two-token name before `goal` alone would be considered.
    """
    try:
        tokens = shlex.split(line)
    except ValueError as error:  # unbalanced quotes
        raise CommandArgumentError(f"Invalid quoting: {error}") from error
    if not tokens:
        return None
    name, args = tokens[0], tuple(tokens[1:])
    if len(tokens) >= 2 and f"{tokens[0]} {tokens[1]}" in COMMAND_SPECS:
        name, args = f"{tokens[0]} {tokens[1]}", tuple(tokens[2:])
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
