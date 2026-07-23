"""CLI exceptions — syntax and routing errors only."""


class CliError(Exception):
    """Base class for CLI-layer errors."""


class UnknownCommandError(CliError):
    """The command name is not in the command registry."""


class CommandArgumentError(CliError):
    """The command was given the wrong arguments."""
