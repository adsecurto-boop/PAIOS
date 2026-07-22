"""The assistant's operation catalog and its one pure computation.

``AssistantTask`` enumerates exactly the mission's permitted read-only
operations and maps each to its prompt template. ``compare_snapshots``
is deterministic arithmetic over two received snapshots — counting and
diffing is presentation, not decision-making; the numbers feed the
comparison prompt and are returned unchanged in the result DTO.
"""

from dataclasses import dataclass
from enum import Enum, unique


@unique
class AssistantTask(Enum):
    EXPLAIN_RECOMMENDATION = "ExplainRecommendation"
    WHY_RECOMMENDATION = "WhyRecommendation"
    EXPLAIN_PRINCIPLE = "ExplainPrinciple"
    EXPLAIN_HABIT = "ExplainHabit"
    SUMMARIZE_TODAY = "SummarizeToday"
    SUMMARIZE_WEEK = "SummarizeWeek"
    COMPARE_SNAPSHOTS = "CompareSnapshots"
    EXPLAIN_TRENDS = "ExplainTrends"
    EXPLAIN_DEEP_WORK = "ExplainDeepWork"
    SUGGEST_STUDY_ORDER = "SuggestStudyOrder"
    SUGGEST_PROJECT_ORDER = "SuggestProjectOrder"
    MARKDOWN_SUMMARY = "MarkdownSummary"
    GENERATE_REPORT = "GenerateReport"
    ANSWER_QUESTION = "AnswerQuestion"
    # Milestone 20 (approved): planning voices — proposal and explanation
    # only; the assistant still never creates, mutates, or schedules.
    CLASSIFY_CAPTURE = "ClassifyCapture"
    EXPLAIN_DAY_PLAN = "ExplainDayPlan"


#: task -> prompt template name (all templates exist in prompts.TEMPLATES).
TASK_TEMPLATES: dict[AssistantTask, str] = {
    AssistantTask.EXPLAIN_RECOMMENDATION: "recommendation_explanation",
    AssistantTask.WHY_RECOMMENDATION: "recommendation_explanation",
    AssistantTask.EXPLAIN_PRINCIPLE: "explain",
    AssistantTask.EXPLAIN_HABIT: "explain",
    AssistantTask.SUMMARIZE_TODAY: "summarize",
    AssistantTask.SUMMARIZE_WEEK: "weekly_review",
    AssistantTask.COMPARE_SNAPSHOTS: "explain",
    AssistantTask.EXPLAIN_TRENDS: "learning_explanation",
    AssistantTask.EXPLAIN_DEEP_WORK: "reflect",
    AssistantTask.SUGGEST_STUDY_ORDER: "learning_explanation",
    AssistantTask.SUGGEST_PROJECT_ORDER: "project_explanation",
    AssistantTask.MARKDOWN_SUMMARY: "summarize",
    AssistantTask.GENERATE_REPORT: "summarize",
    AssistantTask.ANSWER_QUESTION: "explain",
    AssistantTask.CLASSIFY_CAPTURE: "planning_classification",
    AssistantTask.EXPLAIN_DAY_PLAN: "day_plan_explanation",
}


@dataclass(frozen=True)
class SnapshotComparison:
    """A pure, immutable diff of two runtime snapshots (a -> b)."""

    time_a: str
    time_b: str
    execution_context_a: str
    execution_context_b: str
    context_changed: bool
    running_event_a: str | None
    running_event_b: str | None
    running_event_changed: bool
    count_changes: tuple[tuple[str, int, int], ...]  # (field, a, b)

    def as_text(self) -> str:
        """Canonical text form (deterministic; feeds the prompt)."""
        lines = [
            f"Snapshot A at {self.time_a}; Snapshot B at {self.time_b}.",
            f"Execution context: {self.execution_context_a} -> "
            f"{self.execution_context_b}"
            f" ({'changed' if self.context_changed else 'unchanged'})",
            f"Running event: {self.running_event_a or 'none'} -> "
            f"{self.running_event_b or 'none'}"
            f" ({'changed' if self.running_event_changed else 'unchanged'})",
        ]
        for field, count_a, count_b in self.count_changes:
            delta = count_b - count_a
            sign = "+" if delta >= 0 else ""
            lines.append(f"{field}: {count_a} -> {count_b} ({sign}{delta})")
        return "\n".join(lines)


_COUNTED_FIELDS = (
    "events",
    "recommendations",
    "goals",
    "projects",
    "resources",
    "contexts",
    "reflections",
    "principles",
)


def compare_snapshots(snapshot_a, snapshot_b) -> SnapshotComparison:
    """Deterministic diff of two duck-typed RuntimeSnapshots."""

    def _time(snapshot) -> str:
        moment = getattr(snapshot, "current_time", None)
        return moment.isoformat() if moment is not None else "-"

    def _context_name(snapshot) -> str:
        return type(getattr(snapshot, "execution_context", None)).__name__

    def _running(snapshot) -> str | None:
        event = getattr(snapshot, "running_event", None)
        if event is None:
            return None
        return str(getattr(event, "description", event))

    def _count(snapshot, field) -> int:
        return len(tuple(getattr(snapshot, field, ()) or ()))

    return SnapshotComparison(
        time_a=_time(snapshot_a),
        time_b=_time(snapshot_b),
        execution_context_a=_context_name(snapshot_a),
        execution_context_b=_context_name(snapshot_b),
        context_changed=_context_name(snapshot_a) != _context_name(snapshot_b),
        running_event_a=_running(snapshot_a),
        running_event_b=_running(snapshot_b),
        running_event_changed=_running(snapshot_a) != _running(snapshot_b),
        count_changes=tuple(
            (field, _count(snapshot_a, field), _count(snapshot_b, field))
            for field in _COUNTED_FIELDS
        ),
    )
