"""CLI entry point: one-shot commands and the interactive shell.

Each process composes its own Application (composition-root privilege via
the Application facade only). One-shot commands auto-start before and
auto-stop after execution; `paios shell` keeps one started Application
alive across commands (started explicitly with `start`).
"""

import sys
from typing import TextIO

from paios.application.application import Application
from paios.application.config import ApplicationConfig
from paios.cli.commands import CommandProcessor
from paios.cli.exceptions import CliError
from paios.cli.formatter import format_help
from paios.cli.interactive import Shell
from paios.cli.parser import COMMAND_SPECS, ParsedCommand, parse_line


def _split_options(argv: list[str]) -> tuple[ApplicationConfig, list[str]]:
    data_dir = ".data"
    rest: list[str] = []
    index = 0
    while index < len(argv):
        if argv[index] == "--data-dir" and index + 1 < len(argv):
            data_dir = argv[index + 1]
            index += 2
        else:
            rest.append(argv[index])
            index += 1
    return ApplicationConfig(data_dir=data_dir), rest


def main(
    argv: list[str] | None = None,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
) -> int:
    argv = list(sys.argv[1:]) if argv is None else list(argv)
    out = output_stream if output_stream is not None else sys.stdout
    config, arguments = _split_options(argv)

    if not arguments:
        out.write(format_help(COMMAND_SPECS) + "\n")
        return 0

    application = Application(config)
    processor = CommandProcessor(application)

    if arguments[0] == "shell":
        source = input_stream if input_stream is not None else sys.stdin
        Shell(processor, source, out).run()
        if application.started:
            application.stop()
        return 0

    try:
        command = parse_line(" ".join(arguments))
        if command is None:
            out.write(format_help(COMMAND_SPECS) + "\n")
            return 0
        needs_app = command.name not in ("help", "start", "stop")
        if needs_app or command.name == "stop":
            application.start()
        out.write(processor.execute(command) + "\n")
        if application.started:
            application.stop()
        return 0
    except CliError as error:
        out.write(f"Error: {error}\n")
        return 1
    except Exception as error:
        out.write(f"Error: {error}\n")
        if application.started:
            application.stop()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
