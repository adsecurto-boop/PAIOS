"""Routing, delegation, and formatting — every command delegates exactly
one primary Application call; the formatter owns presentation."""

import pytest

from paios.cli.exceptions import CommandArgumentError
from paios.cli.parser import parse_line

from tests.application.conftest import USER


def run(processor, line: str) -> str:
    return processor.execute(parse_line(line))


class TestDelegation:
    """The recording fake proves each command's single primary delegation."""

    @pytest.mark.parametrize(
        "line, method",
        [
            ("start", "start"),
            ("stop", "stop"),
            ("accept 1", "accept_recommendation"),
            ("accept rec_direct", "accept_recommendation"),
            ("reject 1", "reject_recommendation"),
            ("start-event evt_x", "start_event"),
            ("pause-event evt_x", "pause_event"),
            ("resume-event evt_x", "resume_event"),
            ("complete-event evt_x", "complete_event"),
            ("cancel-event evt_x", "cancel_event"),
        ],
    )
    def test_command_delegates_to_exactly_one_primary_method(
        self, recording, line, method
    ):
        fake, processor = recording
        run(processor, line)
        assert len(fake.called(method)) == 1

    def test_index_resolution_uses_the_listing(self, recording):
        fake, processor = recording
        run(processor, "accept 1")
        (call,) = fake.called("accept_recommendation")
        assert call[1][0] == "rec_stub"

    def test_complete_event_passes_free_text_outcome(self, recording):
        fake, processor = recording
        run(processor, "complete-event evt_x rested and recovered")
        (call,) = fake.called("complete_event")
        assert call[1][1] == "rested and recovered"

    def test_out_of_range_index_rejected(self, recording):
        fake, processor = recording
        with pytest.raises(CommandArgumentError, match="No recommendation"):
            run(processor, "accept 9")
        assert fake.called("accept_recommendation") == []


class TestEndToEndCommands:
    """Real application: the full golden path through CLI commands."""

    def test_status_and_snapshot(self, processor):
        status_output = run(processor, "status")
        assert "State:             Running" in status_output
        snapshot_output = run(processor, "snapshot")
        assert "Recommendations:" in snapshot_output

    def test_tick_then_accept_then_execute(self, processor):
        tick_output = run(processor, "tick")
        assert "Energy is low" in tick_output
        assert "principles: Protect Health" in tick_output
        listing = run(processor, "recommendations")
        assert "1. [Pending]" in listing
        assert run(processor, "accept 1") == "Recommendation accepted."
        events = run(processor, "events")
        assert "1. [Ready]" in events
        assert run(processor, "start-event 1") == "Event started."
        assert (
            run(processor, "complete-event 1 slept well")
            == "Event completed."
        )
        detail = run(processor, "event 1")
        assert "Status:       Completed" in detail
        assert "Actual:       slept well" in detail

    def test_reject_flow(self, processor):
        run(processor, "tick")
        assert run(processor, "reject 1") == "Recommendation rejected."
        assert run(processor, "recommendations") == "No active recommendations."

    def test_context_and_projects_and_reflect(self, processor):
        context_output = run(processor, "context")
        assert "1. Office" in context_output
        assert run(processor, "projects") == "No projects."
        assert run(processor, "reflect") == "No reflections recorded."

    def test_disturb_command(self, processor):
        output = run(
            processor, "disturb Work High Team Lead requested overtime"
        )
        assert "Disturbance recorded" in output
        assert "[High]" in output
        assert "Team Lead requested overtime" in output

    def test_disturb_rejects_unknown_enum_values(self, processor):
        with pytest.raises(CommandArgumentError, match="Unknown type"):
            run(processor, "disturb Meteor High something happened")
        with pytest.raises(CommandArgumentError, match="Unknown severity"):
            run(processor, "disturb Work Extreme something happened")

    def test_debug_targets(self, processor):
        assert "State:             Running" in run(processor, "debug runtime")
        assert "Scheduler state:" in run(processor, "debug scheduler")
        assert "Kernel state:   Running" in run(processor, "debug kernel")
        assert "Event bus subscribers:" in run(processor, "debug bus")

    def test_debug_rejects_unknown_target(self, processor):
        with pytest.raises(CommandArgumentError, match="Unknown debug target"):
            run(processor, "debug universe")


class TestFormatterQualities:
    def test_no_ansi_colour_anywhere(self, processor):
        for line in (
            "status",
            "snapshot",
            "tick",
            "recommendations",
            "events",
            "context",
            "help",
        ):
            assert "\x1b" not in run(processor, line)

    def test_no_json_in_output(self, processor):
        run(processor, "tick")
        for line in ("status", "recommendations", "events"):
            output = run(processor, line)
            assert not output.strip().startswith("{")
            assert not output.strip().startswith("[")

    def test_help_lists_every_command(self, processor):
        output = run(processor, "help")
        for name in ("start-event", "disturb", "debug", "recommendations"):
            assert name in output

    def test_help_for_single_command(self, processor):
        output = run(processor, "help accept")
        assert "accept <ref>" in output

    def test_help_for_unknown_command(self, processor):
        assert "Unknown command" in run(processor, "help bogus")
