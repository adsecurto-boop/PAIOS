"""The interactive shell and the entry point."""

import io

from paios.application.application import Application
from paios.application.config import ApplicationConfig
from paios.cli.commands import CommandProcessor
from paios.cli.interactive import Shell
from paios.cli.main import main
from paios.repositories.factory import RepositoryFactory
from paios.runtime.clock import ManualClock

from tests.application.conftest import T0, seed_rest_scenario


def run_shell(tmp_path, script: str) -> str:
    data_dir = tmp_path / "data"
    factory = RepositoryFactory(data_dir)
    factory.initialize()
    seed_rest_scenario(factory)
    application = Application(
        ApplicationConfig(data_dir=data_dir, clock=ManualClock(T0))
    )
    output = io.StringIO()
    Shell(
        CommandProcessor(application), io.StringIO(script), output
    ).run()
    if application.started:
        application.stop()
    return output.getvalue()


class TestShell:
    def test_full_session(self, tmp_path):
        output = run_shell(
            tmp_path,
            "start\n"
            "tick\n"
            "recommendations\n"
            "accept 1\n"
            "start-event 1\n"
            "complete-event 1\n"
            "exit\n",
        )
        assert "PAIOS interactive shell" in output
        assert "PAIOS started." in output
        assert "Energy is low" in output
        assert "Recommendation accepted." in output
        assert "Event started." in output
        assert "Event completed." in output
        assert "Goodbye." in output

    def test_invalid_command_keeps_shell_alive(self, tmp_path):
        output = run_shell(tmp_path, "bogus\nhelp\nexit\n")
        assert "Error: Unknown command: 'bogus'" in output
        assert "PAIOS commands:" in output
        assert "Goodbye." in output

    def test_application_errors_are_reported_not_fatal(self, tmp_path):
        output = run_shell(tmp_path, "status\nstart\nstatus\nexit\n")
        assert "Error: The application is not started" in output
        assert "State:             Running" in output

    def test_blank_lines_ignored(self, tmp_path):
        output = run_shell(tmp_path, "\n\nexit\n")
        assert "Goodbye." in output

    def test_quit_also_exits(self, tmp_path):
        assert "Goodbye." in run_shell(tmp_path, "quit\n")

    def test_end_of_input_exits(self, tmp_path):
        assert "Goodbye." in run_shell(tmp_path, "")


class TestMain:
    def test_no_arguments_prints_help(self, tmp_path):
        output = io.StringIO()
        code = main(
            ["--data-dir", str(tmp_path / "data")], output_stream=output
        )
        assert code == 0
        assert "PAIOS commands:" in output.getvalue()

    def test_one_shot_status_auto_starts_and_stops(self, tmp_path):
        output = io.StringIO()
        code = main(
            ["--data-dir", str(tmp_path / "data"), "status"],
            output_stream=output,
        )
        assert code == 0
        assert "State:             Running" in output.getvalue()

    def test_one_shot_unknown_command_fails_cleanly(self, tmp_path):
        output = io.StringIO()
        code = main(
            ["--data-dir", str(tmp_path / "data"), "bogus"],
            output_stream=output,
        )
        assert code == 1
        assert "Unknown command" in output.getvalue()

    def test_shell_mode_via_main(self, tmp_path):
        output = io.StringIO()
        code = main(
            ["--data-dir", str(tmp_path / "data"), "shell"],
            input_stream=io.StringIO("help\nexit\n"),
            output_stream=output,
        )
        assert code == 0
        assert "PAIOS interactive shell" in output.getvalue()

    def test_one_shot_help(self, tmp_path):
        output = io.StringIO()
        code = main(["help"], output_stream=output)
        assert code == 0
        assert "PAIOS commands:" in output.getvalue()
