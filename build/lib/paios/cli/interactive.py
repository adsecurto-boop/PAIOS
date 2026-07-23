"""Interactive shell: a line-based REPL over injectable streams.

The shell parses, routes, prints, and survives errors — nothing more.
"""

from typing import TextIO

from paios.cli.commands import CommandProcessor, build_dashboard_config
from paios.cli.exceptions import CliError
from paios.cli.parser import parse_line
from paios.dashboard import Dashboard

PROMPT = "> "
EXIT_COMMANDS = ("exit", "quit")


class Shell:
    def __init__(
        self,
        processor: CommandProcessor,
        input_stream: TextIO,
        output_stream: TextIO,
    ) -> None:
        self._processor = processor
        self._in = input_stream
        self._out = output_stream

    def _write(self, text: str) -> None:
        self._out.write(text + "\n")

    def run(self) -> None:
        self._write("PAIOS interactive shell. Type 'help' or 'exit'.")
        while True:
            self._out.write(PROMPT)
            self._out.flush()
            line = self._in.readline()
            if not line:  # end of input stream
                break
            line = line.strip()
            if not line:
                continue
            if line.split()[0] in EXIT_COMMANDS:
                break
            try:
                command = parse_line(line)
                if command is None:
                    continue
                if command.name == "dashboard":
                    # Stream-bound: the dashboard takes over this shell's
                    # output until Ctrl+C, then the prompt returns.
                    Dashboard(
                        self._processor.application,
                        build_dashboard_config(command.args),
                        output_stream=self._out,
                    ).run()
                    continue
                self._write(self._processor.execute(command))
            except CliError as error:
                self._write(f"Error: {error}")
            except Exception as error:  # keep the shell alive
                self._write(f"Error: {error}")
        self._write("Goodbye.")
