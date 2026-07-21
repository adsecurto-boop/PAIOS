"""Parser: names, arity, blank lines, help specs."""

import pytest

from paios.cli.exceptions import CommandArgumentError, UnknownCommandError
from paios.cli.parser import COMMAND_SPECS, parse_line


class TestParsing:
    def test_simple_command(self):
        command = parse_line("status")
        assert command.name == "status"
        assert command.args == ()

    def test_command_with_argument(self):
        command = parse_line("accept 1")
        assert command.name == "accept"
        assert command.args == ("1",)

    def test_free_text_tail(self):
        command = parse_line("disturb Work High production issue escalated")
        assert command.args == (
            "Work",
            "High",
            "production",
            "issue",
            "escalated",
        )

    def test_blank_line_is_none(self):
        assert parse_line("") is None
        assert parse_line("   ") is None

    def test_unknown_command_rejected(self):
        with pytest.raises(UnknownCommandError, match="bogus"):
            parse_line("bogus")

    def test_missing_argument_rejected_with_usage(self):
        with pytest.raises(CommandArgumentError, match="Usage: accept <ref>"):
            parse_line("accept")

    def test_extra_argument_rejected(self):
        with pytest.raises(CommandArgumentError):
            parse_line("status now please")

    def test_disturb_requires_three_arguments(self):
        with pytest.raises(CommandArgumentError):
            parse_line("disturb Work High")


class TestCommandRegistry:
    def test_all_mission_commands_registered(self):
        expected = {
            "start", "stop", "status", "snapshot", "tick",
            "recommendations", "accept", "reject",
            "events", "event", "start-event", "pause-event",
            "resume-event", "complete-event", "cancel-event",
            "context", "projects", "reflect", "disturb", "debug", "help",
        }
        # Milestone 10 adds entity-management commands on top; every
        # original mission command must remain registered unchanged.
        assert expected <= set(COMMAND_SPECS)

    def test_every_spec_has_usage_and_description(self):
        for spec in COMMAND_SPECS.values():
            assert spec.usage
            assert spec.description
