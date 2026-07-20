"""PAIOS CLI — the first Human Interface (Milestone 7).

The CLI owns ONLY parsing, syntax validation, command routing, output
formatting, the interactive shell, and help. Every command performs
exactly one primary delegation into the Application facade; the CLI never
edits entities, runtime state, repositories, or snapshots, and contains
zero business logic.
"""

from paios.cli.commands import CommandProcessor
from paios.cli.exceptions import (
    CliError,
    CommandArgumentError,
    UnknownCommandError,
)
from paios.cli.interactive import Shell
from paios.cli.main import main
from paios.cli.parser import COMMAND_SPECS, ParsedCommand, parse_line

__all__ = [
    "COMMAND_SPECS",
    "CliError",
    "CommandArgumentError",
    "CommandProcessor",
    "ParsedCommand",
    "Shell",
    "UnknownCommandError",
    "main",
    "parse_line",
]
