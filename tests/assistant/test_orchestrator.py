"""Every permitted operation through the pipeline; immutability; no
mutation of inputs; the boundary behaviours."""

import json
from types import SimpleNamespace

import pytest

from paios.assistant import (
    AssistantOrchestrator,
    AssistantTask,
    NullAdapter,
    ResponseParseError,
)

from tests.assistant.conftest import RecordingAdapter


@pytest.fixture
def recording():
    return RecordingAdapter()


@pytest.fixture
def orchestrator(recording):
    return AssistantOrchestrator(recording)


class TestOperations:
    def test_explain_recommendation(
        self, orchestrator, recording, recommendation, snapshot, principle
    ):
        result = orchestrator.explain_recommendation(
            recommendation, snapshot=snapshot, principles=(principle,)
        )
        assert result.task is AssistantTask.EXPLAIN_RECOMMENDATION
        assert result.answer == "A grounded answer."
        assert result.adapter == "recording"
        prompt = recording.requests[0].user_prompt
        assert "rest to recover" in prompt
        assert "Health first" in prompt
        assert "Do not accept, reject, or rank it" in prompt

    def test_why_recommendation_uses_the_why_angle(
        self, orchestrator, recording, recommendation
    ):
        orchestrator.why_recommendation(recommendation)
        assert "why this recommendation exists" in (
            recording.requests[0].user_prompt
        )

    def test_explain_principle_and_habit(
        self, orchestrator, recording, principle, habit, reflections
    ):
        orchestrator.explain_principle(principle)
        orchestrator.explain_habit(habit, reflections=reflections)
        assert "Health first" in recording.requests[0].user_prompt
        assert "Morning study" in recording.requests[1].user_prompt
        assert "Breaks work" in recording.requests[1].user_prompt

    def test_summaries(
        self, orchestrator, recording, snapshot, events, learning_result
    ):
        today = orchestrator.summarize_today(snapshot=snapshot, events=events)
        week = orchestrator.summarize_week(
            events=events, learning_result=learning_result
        )
        assert today.task is AssistantTask.SUMMARIZE_TODAY
        assert week.task is AssistantTask.SUMMARIZE_WEEK
        assert "Scope: today" in recording.requests[0].user_prompt
        assert "weekly review" in recording.requests[1].user_prompt
        assert "Focus rising week over week" in (
            recording.requests[1].user_prompt
        )

    def test_compare_snapshots_carries_the_pure_diff(
        self, orchestrator, snapshot, later_snapshot
    ):
        result = orchestrator.compare_snapshots(snapshot, later_snapshot)
        comparison = result.comparison
        assert comparison is not None
        assert comparison.time_a == "2026-07-20T09:00:00"
        assert comparison.time_b == "2026-07-22T09:00:00"
        assert comparison.running_event_changed is True
        assert comparison.running_event_b == "Deep work"
        counts = dict(
            (field, (a, b)) for field, a, b in comparison.count_changes
        )
        assert counts["events"] == (2, 3)
        assert counts["recommendations"] == (0, 1)
        assert "events: 2 -> 3 (+1)" in comparison.as_text()

    def test_trends_deep_work_and_orders(
        self,
        orchestrator,
        recording,
        learning_result,
        events,
        knowledge_items,
        projects,
    ):
        orchestrator.explain_trends(learning_result)
        orchestrator.explain_deep_work(events)
        orchestrator.suggest_study_order(knowledge_items)
        orchestrator.suggest_project_order(projects)
        assert "trends" in recording.requests[0].user_prompt
        assert "Deep work" in recording.requests[1].user_prompt
        study_prompt = recording.requests[2].user_prompt
        assert "Boundary analysis" in study_prompt
        assert "nothing is scheduled" in study_prompt
        project_prompt = recording.requests[3].user_prompt
        assert "PAIOS" in project_prompt and "Garden" in project_prompt

    def test_documents_and_questions(
        self, orchestrator, recording, snapshot, events
    ):
        markdown = orchestrator.markdown_summary(
            snapshot=snapshot, events=events
        )
        report = orchestrator.generate_report(events=events)
        answer = orchestrator.answer_question(
            "What did I complete?", snapshot=snapshot, events=events
        )
        assert markdown.task is AssistantTask.MARKDOWN_SUMMARY
        assert report.task is AssistantTask.GENERATE_REPORT
        assert answer.task is AssistantTask.ANSWER_QUESTION
        assert "Markdown" in recording.requests[0].user_prompt
        assert "report" in recording.requests[1].user_prompt
        assert "What did I complete?" in recording.requests[2].user_prompt


class TestResultContract:
    def test_results_are_immutable(self, orchestrator, recommendation):
        result = orchestrator.explain_recommendation(recommendation)
        with pytest.raises(AttributeError):
            result.answer = "changed"
        with pytest.raises(AttributeError):
            result.task = AssistantTask.GENERATE_REPORT
        assert isinstance(result.bullets, tuple)

    def test_prompt_determinism_across_runs(
        self, recommendation, snapshot, principle
    ):
        first_adapter = RecordingAdapter()
        second_adapter = RecordingAdapter()
        kwargs = dict(snapshot=snapshot, principles=(principle,))
        AssistantOrchestrator(first_adapter).explain_recommendation(
            recommendation, **kwargs
        )
        AssistantOrchestrator(second_adapter).explain_recommendation(
            recommendation, **kwargs
        )
        assert (
            first_adapter.requests[0].user_prompt
            == second_adapter.requests[0].user_prompt
        )
        assert (
            first_adapter.requests[0].system_prompt
            == second_adapter.requests[0].system_prompt
        )

    def test_inputs_are_never_mutated(
        self, orchestrator, snapshot, later_snapshot, recommendation
    ):
        before = {
            "snapshot": dict(vars(snapshot)),
            "later": dict(vars(later_snapshot)),
            "recommendation": dict(vars(recommendation)),
        }
        orchestrator.compare_snapshots(snapshot, later_snapshot)
        orchestrator.explain_recommendation(
            recommendation, snapshot=snapshot
        )
        assert dict(vars(snapshot)) == before["snapshot"]
        assert dict(vars(later_snapshot)) == before["later"]
        assert dict(vars(recommendation)) == before["recommendation"]

    def test_null_adapter_end_to_end(self, recommendation):
        result = AssistantOrchestrator(NullAdapter()).explain_recommendation(
            recommendation
        )
        assert result.adapter == "null"
        assert "[offline]" in result.answer

    def test_malformed_adapter_reply_raises_parse_error(self, recommendation):
        broken = RecordingAdapter(reply="I feel like chatting instead.")
        with pytest.raises(ResponseParseError):
            AssistantOrchestrator(broken).explain_recommendation(
                recommendation
            )

    def test_missing_fields_in_reply_raise(self, recommendation):
        broken = RecordingAdapter(reply=json.dumps({"bullets": ["x"]}))
        with pytest.raises(ResponseParseError, match="answer"):
            AssistantOrchestrator(broken).explain_recommendation(
                recommendation
            )

    def test_orchestrator_holds_only_the_adapter(self, recording):
        orchestrator = AssistantOrchestrator(recording)
        assert set(vars(orchestrator)) == {"_adapter"}


class TestRealSnapshots:
    """The duck-typed reading matches genuine PAIOS objects.

    Tests may import paios freely — the boundary rule binds the
    assistant package, not its tests."""

    @pytest.fixture
    def application(self, tmp_path):
        from paios.application.application import Application
        from paios.application.config import ApplicationConfig
        from paios.repositories.factory import RepositoryFactory
        from paios.runtime.clock import ManualClock

        from tests.application.conftest import T0, seed_rest_scenario

        data_dir = tmp_path / "data"
        factory = RepositoryFactory(data_dir)
        factory.initialize()
        seed_rest_scenario(factory)
        application = Application(
            ApplicationConfig(data_dir=data_dir, clock=ManualClock(T0))
        )
        application.start()
        yield application
        if application.started:
            application.stop()

    def test_summarize_and_compare_with_real_runtime_snapshots(
        self, application
    ):
        adapter = RecordingAdapter()
        orchestrator = AssistantOrchestrator(adapter)
        before = application.snapshot()
        application.tick()  # generates the rest recommendation
        after = application.snapshot()

        summary = orchestrator.summarize_today(
            snapshot=after,
            events=application.list_events(),
            goals=application.list_goals(),
            resources=application.list_resources(),
        )
        assert summary.answer == "A grounded answer."
        assert "Energy" in adapter.requests[0].user_prompt

        result = orchestrator.compare_snapshots(before, after)
        counts = dict(
            (field, (a, b)) for field, a, b in result.comparison.count_changes
        )
        assert counts["recommendations"][1] >= 1

    def test_explain_real_recommendation(self, application):
        adapter = RecordingAdapter()
        application.tick()
        recommendation = application.active_recommendations()[0]
        result = AssistantOrchestrator(adapter).why_recommendation(
            recommendation, snapshot=application.snapshot()
        )
        assert result.task is AssistantTask.WHY_RECOMMENDATION
        assert "rest to recover" in adapter.requests[0].user_prompt
