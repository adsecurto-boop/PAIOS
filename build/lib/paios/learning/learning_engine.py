"""The Learning Engine: one pure, deterministic analysis pass.

    History -> extract -> patterns -> trends -> reflections/insights ->
    candidates -> LearningResult (reports + summaries)

Stateless and side-effect free: the history is never mutated (the engine
holds no references back into it beyond the immutable evidence it quotes),
nothing is persisted, nothing is scheduled, and no clock is read — every
timestamp derives from the evidence or the caller-supplied anchor.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from paios.domain.entities.insight import Insight
from paios.domain.enums import ImpactType
from paios.learning.analyzer import (
    Finding,
    Trend,
    analyze_patterns,
    analyze_trends,
)
from paios.learning.extractor import (
    Observations,
    anchor_time,
    category_of,
    extract,
    resolve_as_of,
)
from paios.learning.habit_analyzer import (
    CandidateHabitChange,
    propose_habit_changes,
)
from paios.learning.history import History
from paios.learning.principle_generator import (
    CandidatePrinciple,
    propose_principles,
)
from paios.learning.reflection_engine import (
    ReflectionQuality,
    analyze_reflections,
)

WEEKLY_DAYS = 7
MONTHLY_DAYS = 30


@dataclass(frozen=True)
class PeriodSummary:
    """A deterministic period digest (weekly/monthly)."""

    label: str
    period_start: datetime
    period_end: datetime
    completed: int
    skipped: int
    cancelled: int
    opportunity_minutes: int
    distraction_minutes: int
    top_category: str | None


@dataclass(frozen=True)
class LearningReport:
    generated_at: datetime | None
    events_observed: int
    completed: int
    skipped: int
    cancelled: int
    interrupted: int
    findings: tuple[Finding, ...]
    reflection_quality: ReflectionQuality
    insight_count: int
    candidate_principle_count: int
    candidate_habit_change_count: int


@dataclass(frozen=True)
class TrendReport:
    generated_at: datetime | None
    trends: tuple[Trend, ...]


@dataclass(frozen=True)
class LearningResult:
    """Everything one learning pass produced — immutable and replayable."""

    generated_at: datetime | None
    findings: tuple[Finding, ...]
    trends: tuple[Trend, ...]
    insights: tuple[Insight, ...]
    reflection_quality: ReflectionQuality
    candidate_principles: tuple[CandidatePrinciple, ...]
    candidate_habit_changes: tuple[CandidateHabitChange, ...]
    learning_report: LearningReport
    trend_report: TrendReport
    weekly_summary: PeriodSummary | None
    monthly_summary: PeriodSummary | None


def _period_summary(
    label: str,
    observations: Observations,
    end: datetime,
    days: int,
) -> PeriodSummary:
    start = end - timedelta(days=days)

    def within(event) -> bool:
        moment = anchor_time(event)
        return moment is not None and start < moment <= end

    completed = tuple(filter(within, observations.completed))
    opportunity = sum(
        event.duration.minutes
        for event in completed
        if event.impact_type is ImpactType.OPPORTUNITY
        and event.duration is not None
    )
    distraction = sum(
        event.duration.minutes
        for event in completed
        if event.impact_type is ImpactType.DISTRACTION
        and event.duration is not None
    )
    counts: dict[str, int] = {}
    for event in completed:
        counts[category_of(event)] = counts.get(category_of(event), 0) + 1
    top_category = (
        min(
            (category for category in counts),
            key=lambda category: (-counts[category], category),
        )
        if counts
        else None
    )
    return PeriodSummary(
        label=label,
        period_start=start,
        period_end=end,
        completed=len(completed),
        skipped=sum(1 for e in observations.skipped if within(e)),
        cancelled=sum(1 for e in observations.cancelled if within(e)),
        opportunity_minutes=opportunity,
        distraction_minutes=distraction,
        top_category=top_category,
    )


class LearningEngine:
    """Stateless: holds nothing between invocations."""

    def learn(
        self, history: History, as_of: datetime | None = None
    ) -> LearningResult:
        observations = extract(history, as_of)
        generated_at = resolve_as_of(history, as_of)

        findings = analyze_patterns(history, observations)
        trends = analyze_trends(history, observations)
        insights, reflection_quality = analyze_reflections(history)
        candidate_principles = propose_principles(
            history, observations, findings
        )
        candidate_habit_changes = propose_habit_changes(
            history, observations, findings
        )

        learning_report = LearningReport(
            generated_at=generated_at,
            events_observed=len(history.events),
            completed=len(observations.completed),
            skipped=len(observations.skipped),
            cancelled=len(observations.cancelled),
            interrupted=len(observations.interrupted),
            findings=findings,
            reflection_quality=reflection_quality,
            insight_count=len(insights),
            candidate_principle_count=len(candidate_principles),
            candidate_habit_change_count=len(candidate_habit_changes),
        )
        trend_report = TrendReport(generated_at=generated_at, trends=trends)
        weekly = monthly = None
        if generated_at is not None:
            weekly = _period_summary(
                "Weekly", observations, generated_at, WEEKLY_DAYS
            )
            monthly = _period_summary(
                "Monthly", observations, generated_at, MONTHLY_DAYS
            )
        return LearningResult(
            generated_at=generated_at,
            findings=findings,
            trends=trends,
            insights=insights,
            reflection_quality=reflection_quality,
            candidate_principles=candidate_principles,
            candidate_habit_changes=candidate_habit_changes,
            learning_report=learning_report,
            trend_report=trend_report,
            weekly_summary=weekly,
            monthly_summary=monthly,
        )
