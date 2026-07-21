"""The orchestrator: snapshot -> context -> template -> adapter -> parser.

One public method per permitted operation (the mission's list). Each
method composes a deterministic prompt from received immutable inputs,
asks the adapter for text, parses and validates it, and returns a
frozen AssistantResult. The orchestrator holds exactly one collaborator
— the adapter — and never touches PAIOS: no repositories, no scheduler,
no runtime, no decision engine, no persistence, no mutation. What the
user does with a result is the caller's business (the Application
decides; the assistant only speaks).
"""

from dataclasses import dataclass

from paios.assistant import context_builder, prompts
from paios.assistant.adapters import LlmAdapter
from paios.assistant.response_parser import ParsedResponse, parse_response
from paios.assistant.tools import (
    TASK_TEMPLATES,
    AssistantTask,
    SnapshotComparison,
    compare_snapshots,
)


@dataclass(frozen=True)
class AssistantRequest:
    """What an adapter receives: fully composed, immutable."""

    task: AssistantTask
    template_name: str
    system_prompt: str
    user_prompt: str


@dataclass(frozen=True)
class AssistantResult:
    """What every operation returns: a plain immutable DTO."""

    task: AssistantTask
    answer: str
    bullets: tuple[str, ...]
    confidence: float | None
    adapter: str
    prompt: str
    raw_response: str
    #: Present only for snapshot comparisons (the pure diff).
    comparison: SnapshotComparison | None = None


class AssistantOrchestrator:
    def __init__(self, adapter: LlmAdapter) -> None:
        self._adapter = adapter

    # --- the pipeline -----------------------------------------------------

    def _run(
        self,
        task: AssistantTask,
        comparison: SnapshotComparison | None = None,
        **fields: str,
    ) -> AssistantResult:
        template = prompts.TEMPLATES[TASK_TEMPLATES[task]]
        user_prompt = template.render(**fields)
        request = AssistantRequest(
            task=task,
            template_name=template.name,
            system_prompt=template.system,
            user_prompt=user_prompt,
        )
        raw = self._adapter.complete(request)
        parsed: ParsedResponse = parse_response(raw)
        return AssistantResult(
            task=task,
            answer=parsed.answer,
            bullets=parsed.bullets,
            confidence=parsed.confidence,
            adapter=self._adapter.name,
            prompt=user_prompt,
            raw_response=raw,
            comparison=comparison,
        )

    # --- recommendations --------------------------------------------------

    def explain_recommendation(
        self, recommendation, snapshot=None, principles=()
    ) -> AssistantResult:
        return self._run(
            AssistantTask.EXPLAIN_RECOMMENDATION,
            angle="what this recommendation means and what following it "
            "would look like",
            subject=context_builder.recommendation_line(recommendation),
            context=context_builder.build_context(
                snapshot=snapshot, principles=tuple(principles)
            ),
        )

    def why_recommendation(
        self, recommendation, snapshot=None, principles=(), habits=()
    ) -> AssistantResult:
        return self._run(
            AssistantTask.WHY_RECOMMENDATION,
            angle="why this recommendation exists — which principles, "
            "resource levels and situation likely led the Decision Engine "
            "to produce it",
            subject=context_builder.recommendation_line(recommendation),
            context=context_builder.build_context(
                snapshot=snapshot,
                principles=tuple(principles),
                habits=tuple(habits),
            ),
        )

    # --- principles / habits ----------------------------------------------

    def explain_principle(self, principle, snapshot=None) -> AssistantResult:
        return self._run(
            AssistantTask.EXPLAIN_PRINCIPLE,
            subject=context_builder.principle_line(principle),
            context=context_builder.build_context(snapshot=snapshot),
            question="What does this principle mean for the user's days?",
        )

    def explain_habit(self, habit, reflections=()) -> AssistantResult:
        return self._run(
            AssistantTask.EXPLAIN_HABIT,
            subject=context_builder.habit_line(habit),
            context=context_builder.build_context(
                reflections=tuple(reflections)
            ),
            question="What does this habit and its trend mean?",
        )

    # --- summaries ----------------------------------------------------------

    def summarize_today(
        self, snapshot=None, events=(), goals=(), projects=(), resources=()
    ) -> AssistantResult:
        return self._run(
            AssistantTask.SUMMARIZE_TODAY,
            scope="today",
            context=context_builder.build_context(
                snapshot=snapshot,
                events=tuple(events),
                goals=tuple(goals),
                projects=tuple(projects),
                resources=tuple(resources),
            ),
        )

    def summarize_week(
        self,
        events=(),
        reflections=(),
        learning_result=None,
        goals=(),
        projects=(),
    ) -> AssistantResult:
        return self._run(
            AssistantTask.SUMMARIZE_WEEK,
            context=context_builder.build_context(
                learning_result=learning_result,
                events=tuple(events),
                reflections=tuple(reflections),
                goals=tuple(goals),
                projects=tuple(projects),
            ),
        )

    # --- comparison / trends ------------------------------------------------

    def compare_snapshots(self, snapshot_a, snapshot_b) -> AssistantResult:
        comparison = compare_snapshots(snapshot_a, snapshot_b)
        return self._run(
            AssistantTask.COMPARE_SNAPSHOTS,
            comparison=comparison,
            subject="A comparison of two runtime snapshots (A -> B):\n"
            + comparison.as_text(),
            context=context_builder.build_context(snapshot=snapshot_b),
            question="What changed between the two snapshots, and what "
            "does the change suggest?",
        )

    def explain_trends(self, learning_result) -> AssistantResult:
        return self._run(
            AssistantTask.EXPLAIN_TRENDS,
            instruction="Explain the trends this learning pass surfaced "
            "and what they suggest, as observations only.",
            context=context_builder.build_context(
                learning_result=learning_result
            ),
        )

    def explain_deep_work(self, events, reflections=()) -> AssistantResult:
        return self._run(
            AssistantTask.EXPLAIN_DEEP_WORK,
            context=context_builder.build_context(
                events=tuple(events), reflections=tuple(reflections)
            ),
        )

    # --- suggestions (ordering as language, never as commands) --------------

    def suggest_study_order(self, knowledge) -> AssistantResult:
        return self._run(
            AssistantTask.SUGGEST_STUDY_ORDER,
            instruction="Suggest an order in which to revise these "
            "knowledge items, with a short reason per item. This is a "
            "suggestion for the user to weigh — nothing is scheduled.",
            context=context_builder.build_context(
                knowledge=tuple(knowledge)
            ),
        )

    def suggest_project_order(
        self, projects, goals=()
    ) -> AssistantResult:
        return self._run(
            AssistantTask.SUGGEST_PROJECT_ORDER,
            instruction="Suggest an order in which to attend to these "
            "projects, with a short reason per project. This is a "
            "suggestion for the user to weigh — nothing is scheduled.",
            subject="\n".join(
                context_builder.project_line(project)
                for project in sorted(
                    projects, key=lambda p: str(getattr(p, "name", p))
                )
            )
            or "(none)",
            context=context_builder.build_context(goals=tuple(goals)),
        )

    # --- documents -----------------------------------------------------------

    def markdown_summary(self, **inputs) -> AssistantResult:
        return self._document(AssistantTask.MARKDOWN_SUMMARY, **inputs)

    def generate_report(self, **inputs) -> AssistantResult:
        return self._document(AssistantTask.GENERATE_REPORT, **inputs)

    def _document(self, task: AssistantTask, **inputs) -> AssistantResult:
        snapshot = inputs.pop("snapshot", None)
        learning_result = inputs.pop("learning_result", None)
        scope = (
            "a Markdown document (the 'answer' field must be valid "
            "Markdown with headings)"
            if task is AssistantTask.MARKDOWN_SUMMARY
            else "a full written report (the 'answer' field holds the "
            "report body in Markdown)"
        )
        return self._run(
            task,
            scope=scope,
            context=context_builder.build_context(
                snapshot=snapshot,
                learning_result=learning_result,
                **{name: tuple(items) for name, items in inputs.items()},
            ),
        )

    # --- questions ------------------------------------------------------------

    def answer_question(self, question: str, **inputs) -> AssistantResult:
        snapshot = inputs.pop("snapshot", None)
        learning_result = inputs.pop("learning_result", None)
        return self._run(
            AssistantTask.ANSWER_QUESTION,
            subject="The user asked a question about their own data.",
            context=context_builder.build_context(
                snapshot=snapshot,
                learning_result=learning_result,
                **{name: tuple(items) for name, items in inputs.items()},
            ),
            question=question,
        )
