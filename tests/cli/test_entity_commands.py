"""Milestone 10 — entity management through the CLI.

The CLI parses, resolves references, and formats; every command performs
exactly one primary delegation into the Application facade. These tests run
real commands over a real started application (seeded rest scenario), plus
one-shot ``main()`` invocations for restart persistence.
"""

from io import StringIO

import pytest

from paios.application.exceptions import DuplicateEntityError
from paios.cli.exceptions import CommandArgumentError, UnknownCommandError
from paios.cli.main import main
from paios.cli.parser import parse_line
from paios.domain.errors import DomainValidationError


def run(processor, line: str) -> str:
    return processor.execute(parse_line(line))


class TestTwoTokenParsing:
    def test_two_token_command_resolves(self):
        command = parse_line("goal list")
        assert command.name == "goal list"
        assert command.args == ()

    def test_quoted_arguments_stay_grouped(self):
        command = parse_line('goal add "Learn Sanskrit" Read fluently')
        assert command.args == ("Learn Sanskrit", "Read", "fluently")

    def test_unbalanced_quote_rejected(self):
        with pytest.raises(CommandArgumentError, match="quoting"):
            parse_line('goal add "Learn')

    def test_single_token_commands_still_parse(self):
        assert parse_line("status").name == "status"

    def test_write_commands_for_habits_do_not_exist(self):
        with pytest.raises(UnknownCommandError):
            parse_line("habit add Running")
        with pytest.raises(UnknownCommandError):
            parse_line("insight add anything")


class TestUserCommands:
    def test_add_list_show(self, processor):
        assert "User added" in run(processor, 'user add Asha')
        assert "Asha" in run(processor, "user list")
        assert "Asha" in run(processor, "user show 1")

    def test_created_user_owns_new_aggregates(self, processor, cli_app):
        run(processor, "user add Asha")
        run(processor, 'goal add "Learn Sanskrit"')
        goal = cli_app.list_goals()[0]
        assert goal.user_id == cli_app.list_users()[0].user_id


class TestGoalCommands:
    def test_full_lifecycle(self, processor):
        assert "Goal added" in run(
            processor, 'goal add "Learn Sanskrit" Read the Gita fluently'
        )
        listing = run(processor, "goal list")
        assert "[Active] Learn Sanskrit" in listing
        detail = run(processor, "goal show 1")
        assert "Read the Gita fluently" in detail
        assert "Goal paused" in run(processor, "goal pause 1")
        assert "Goal resumed" in run(processor, "goal resume 1")
        assert "Goal completed" in run(processor, "goal complete 1")
        assert "[Completed]" in run(processor, "goal list")

    def test_duplicate_add_surfaces_application_error(self, processor):
        run(processor, 'goal add "Learn Sanskrit"')
        with pytest.raises(DuplicateEntityError):
            run(processor, 'goal add "Learn Sanskrit"')

    def test_bad_reference_number(self, processor):
        with pytest.raises(CommandArgumentError, match="No goal number 4"):
            run(processor, "goal show 4")


class TestProjectCommands:
    def test_add_progress_show_complete(self, processor):
        assert "Project added" in run(processor, 'project add PAIOS "Build it"')
        assert "Progress updated: 40%" in run(processor, "project progress 1 40")
        detail = run(processor, "project show 1")
        assert "40%" in detail
        assert "Project completed" in run(processor, "project complete 1")
        assert "[Completed] PAIOS" in run(processor, "project list")

    def test_progress_requires_a_number(self, processor):
        run(processor, "project add PAIOS")
        with pytest.raises(CommandArgumentError, match="percent"):
            run(processor, "project progress 1 lots")

    def test_out_of_bounds_progress_rejected_by_domain(self, processor):
        run(processor, "project add PAIOS")
        with pytest.raises(DomainValidationError):
            run(processor, "project progress 1 150")


class TestPrincipleCommands:
    def test_add_list_show_review(self, processor):
        assert "Principle added" in run(
            processor, 'principle add "Truth first" truth Never self-deceive'
        )
        # The seeded rest scenario already holds the Health principle.
        listing = run(processor, "principle list")
        assert "[Truth] Truth first" in listing
        assert "Never self-deceive" in run(processor, "principle show 2")
        assert "Principle reviewed" in run(processor, "principle review 2")
        assert "Last reviewed:" in run(processor, "principle show 2")

    def test_unknown_category_rejected(self, processor):
        with pytest.raises(CommandArgumentError, match="category"):
            run(processor, 'principle add "Truth first" honesty')


class TestResourceCommands:
    def test_add_consume_produce(self, processor):
        assert "Resource added" in run(processor, "resource add focus 50 points")
        assert "Focus = 30 points" in run(processor, "resource consume 2 20")
        assert "Focus = 35 points" in run(processor, "resource produce 2 5")

    def test_amount_must_be_numeric(self, processor):
        with pytest.raises(CommandArgumentError, match="amount"):
            run(processor, "resource consume 1 much")

    def test_unknown_type_rejected(self, processor):
        with pytest.raises(CommandArgumentError, match="type"):
            run(processor, "resource add mana 10 points")


class TestContextCommands:
    def test_add_with_fields(self, processor):
        assert "Context added" in run(
            processor,
            'context add "Deep Work" location=Library people=Asha,Ravi '
            'notes="phone off"',
        )
        assert "Deep Work @ Library" in run(processor, "context list")
        detail = run(processor, "context show 2")
        assert "Asha, Ravi" in detail
        assert "phone off" in detail

    def test_unknown_field_rejected(self, processor):
        with pytest.raises(CommandArgumentError, match="Unknown field"):
            run(processor, "context add Focus mood=great")

    def test_malformed_field_rejected(self, processor):
        with pytest.raises(CommandArgumentError, match="field=value"):
            run(processor, "context add Focus location")


class TestKnowledgeCommands:
    def test_add_revise_apply(self, processor):
        assert "Knowledge added" in run(
            processor,
            "knowledge add Programming Python Dataclasses confidence=30",
        )
        assert "revision 1" in run(processor, "knowledge revise 1 60")
        assert "confidence 60" in run(processor, "knowledge revise 1 60")
        assert "applied" in run(processor, "knowledge apply 1")
        detail = run(processor, "knowledge show 1")
        assert "Applied:" in detail and "yes" in detail

    def test_project_reference_resolves(self, processor, cli_app):
        run(processor, "project add PAIOS")
        run(processor, "knowledge add Programming Python Dataclasses project=1")
        knowledge = cli_app.list_knowledge()[0]
        assert knowledge.project_id == cli_app.list_projects()[0].project_id


class TestReflectionCommands:
    def complete_event(self, processor):
        run(processor, "tick")
        run(processor, "accept 1")
        run(processor, "start-event 1")
        run(processor, "complete-event 1 rested well")

    def test_reflect_on_completed_event(self, processor):
        self.complete_event(processor)
        assert "Reflection added" in run(
            processor,
            'reflection add 1 lesson_learned="Short rest restores focus" '
            "confidence=0.8",
        )
        assert "Short rest restores focus" in run(processor, "reflection list")
        detail = run(processor, "reflection show 1")
        assert "Short rest restores focus" in detail
        assert "0.8" in detail

    def test_reflection_requires_completed_event(self, processor):
        run(processor, "tick")
        run(processor, "accept 1")
        with pytest.raises(DomainValidationError):
            run(processor, "reflection add 1 facts=early")


class TestArchiveCommand:
    def test_archive_after_completion(self, processor):
        run(processor, "tick")
        run(processor, "accept 1")
        run(processor, "start-event 1")
        run(processor, "complete-event 1")
        assert "Event archived." == run(processor, "archive-event 1")
        assert "[Archived]" in run(processor, "events")


class TestReadOnlyCommands:
    def test_habits_and_insights_list_empty(self, processor):
        assert "No habits detected." == run(processor, "habit list")
        assert "No insights extracted." == run(processor, "insight list")


class TestOneShotPersistence:
    """`main()` composes, starts, executes, stops — entities must survive
    across processes (restart persistence through the real entry point)."""

    def run_main(self, tmp_path, *arguments) -> str:
        output = StringIO()
        exit_code = main(
            ["--data-dir", str(tmp_path / "data"), *arguments],
            output_stream=output,
        )
        assert exit_code == 0, output.getvalue()
        return output.getvalue()

    def test_add_then_list_across_processes(self, tmp_path):
        self.run_main(tmp_path, "goal", "add", "Learn Sanskrit", "Read daily")
        listing = self.run_main(tmp_path, "goal", "list")
        assert "[Active] Learn Sanskrit" in listing

    def test_multi_word_quoted_name_survives_argv(self, tmp_path):
        self.run_main(tmp_path, "context", "add", "Deep Work", "location=Home")
        listing = self.run_main(tmp_path, "context", "list")
        assert "Deep Work @ Home" in listing

    def test_one_shot_error_reports_cleanly(self, tmp_path):
        output = StringIO()
        exit_code = main(
            ["--data-dir", str(tmp_path / "data"), "goal", "show", "9"],
            output_stream=output,
        )
        assert exit_code == 1
        assert "No goal number 9" in output.getvalue()
