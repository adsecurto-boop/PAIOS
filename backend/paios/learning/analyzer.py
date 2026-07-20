"""Pattern and trend analysis — deterministic expert rules over evidence.

Findings are recurring patterns with their evidence; Trends compare the
first and second halves of the analysis window. Thresholds and tolerances
are Domain-Policy constants (evolvable, documented) — never Principles.
"""

from dataclasses import dataclass
from enum import Enum, unique

from paios.domain.enums import (
    DisturberType,
    EventOutcomeType,
    ImpactType,
    ResourceType,
)
from paios.learning.extractor import Observations, anchor_time, category_of
from paios.learning.history import History

# --- Domain-Policy constants ----------------------------------------------
REPEAT_THRESHOLD = 3
DISTURBANCE_THRESHOLD = 3
RATIO_TOLERANCE = 0.05
COUNT_TOLERANCE = 0

#: Category vocabularies for the mandated trend analyses (evolvable).
SMOKING_CATEGORIES = ("smoking", "smoke", "cigarette")
ALCOHOL_CATEGORIES = ("alcohol", "drinking")
STUDY_CATEGORIES = ("study", "learning", "reading")
DEEP_WORK_CATEGORIES = ("focus", "deep work", "deep-work")


@unique
class FindingKind(Enum):
    REPEATED_FAILURE = "Repeated failure"
    REPEATED_SUCCESS = "Repeated success"
    REPEATED_DISTRACTION = "Repeated distraction"
    REWARD_MISUSE = "Reward-system misuse"
    FREQUENT_DISTURBANCE = "Frequent disturbance"


@dataclass(frozen=True)
class Finding:
    kind: FindingKind
    category: str
    count: int
    description: str
    evidence: tuple[str, ...]


@unique
class TrendDirection(Enum):
    IMPROVING = "Improving"
    DECLINING = "Declining"
    STABLE = "Stable"
    INSUFFICIENT_DATA = "Insufficient data"


@dataclass(frozen=True)
class Trend:
    name: str
    direction: TrendDirection
    first_half: float
    second_half: float
    description: str


def _in_categories(event, names: tuple[str, ...]) -> bool:
    category = category_of(event)
    return any(name in category for name in names)


def _event_ids(events) -> tuple[str, ...]:
    return tuple(str(event.event_id) for event in events)


# --- Findings -------------------------------------------------------------


def analyze_patterns(
    history: History, observations: Observations
) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    findings.extend(_repeated_outcomes(observations))
    findings.extend(_repeated_distractions(observations))
    findings.extend(_reward_misuse(history, observations))
    findings.extend(_frequent_disturbances(history))
    return tuple(findings)


def _repeated_outcomes(observations: Observations) -> list[Finding]:
    failures: dict[str, list] = {}
    successes: dict[str, list] = {}
    for event in observations.completed:
        outcome = event.outcome
        if outcome is None:
            continue
        bucket = None
        if outcome.outcome_type is EventOutcomeType.FAILED:
            bucket = failures
        elif outcome.outcome_type is EventOutcomeType.COMPLETED:
            bucket = successes
        if bucket is not None:
            bucket.setdefault(category_of(event), []).append(event)
    findings = []
    for category in sorted(failures):
        events = failures[category]
        if len(events) >= REPEAT_THRESHOLD:
            findings.append(
                Finding(
                    kind=FindingKind.REPEATED_FAILURE,
                    category=category,
                    count=len(events),
                    description=(
                        f"{len(events)} completed '{category}' Events "
                        "recorded a Failed outcome"
                    ),
                    evidence=_event_ids(events),
                )
            )
    for category in sorted(successes):
        events = successes[category]
        if len(events) >= REPEAT_THRESHOLD:
            findings.append(
                Finding(
                    kind=FindingKind.REPEATED_SUCCESS,
                    category=category,
                    count=len(events),
                    description=(
                        f"{len(events)} completed '{category}' Events "
                        "achieved their intended outcome"
                    ),
                    evidence=_event_ids(events),
                )
            )
    return findings


def _repeated_distractions(observations: Observations) -> list[Finding]:
    by_category: dict[str, list] = {}
    for event in observations.completed:
        if event.impact_type is ImpactType.DISTRACTION:
            by_category.setdefault(category_of(event), []).append(event)
    findings = []
    for category in sorted(by_category):
        events = by_category[category]
        if len(events) >= REPEAT_THRESHOLD:
            findings.append(
                Finding(
                    kind=FindingKind.REPEATED_DISTRACTION,
                    category=category,
                    count=len(events),
                    description=(
                        f"'{category}' produced {len(events)} "
                        "Distraction-classified Events"
                    ),
                    evidence=_event_ids(events),
                )
            )
    return findings


def _reward_misuse(
    history: History, observations: Observations
) -> list[Finding]:
    """A Habit with a declared reward whose matching Events skew Distraction:
    the reward is reinforcing the wrong behavior."""
    findings = []
    for habit in sorted(history.habits, key=lambda h: str(h.habit_id)):
        if not habit.reward:
            continue
        name = habit.name.strip().lower()
        matching = [
            event
            for event in observations.completed
            if category_of(event) in (name,) or name in category_of(event)
        ]
        distractions = [
            event
            for event in matching
            if event.impact_type is ImpactType.DISTRACTION
        ]
        if (
            len(matching) >= REPEAT_THRESHOLD
            and len(distractions) * 2 > len(matching)
        ):
            findings.append(
                Finding(
                    kind=FindingKind.REWARD_MISUSE,
                    category=name,
                    count=len(distractions),
                    description=(
                        f"Habit '{habit.name}' carries reward "
                        f"'{habit.reward}' but its Events skew Distraction "
                        f"({len(distractions)}/{len(matching)})"
                    ),
                    evidence=_event_ids(distractions),
                )
            )
    return findings


def _frequent_disturbances(history: History) -> list[Finding]:
    by_type: dict[DisturberType, list] = {}
    for disturber in history.event_disturbers:
        by_type.setdefault(disturber.type, []).append(disturber)
    findings = []
    for disturber_type in sorted(by_type, key=lambda t: t.value):
        disturbers = by_type[disturber_type]
        if len(disturbers) >= DISTURBANCE_THRESHOLD:
            findings.append(
                Finding(
                    kind=FindingKind.FREQUENT_DISTURBANCE,
                    category=disturber_type.value.lower(),
                    count=len(disturbers),
                    description=(
                        f"{len(disturbers)} '{disturber_type.value}' "
                        "disturbances interrupted the plan"
                    ),
                    evidence=tuple(
                        str(d.event_disturber_id) for d in disturbers
                    ),
                )
            )
    return findings


# --- Trends ---------------------------------------------------------------


def _direction(
    first: float, second: float, higher_is_better: bool, tolerance: float
) -> TrendDirection:
    delta = second - first
    if abs(delta) <= tolerance:
        return TrendDirection.STABLE
    improved = delta > 0 if higher_is_better else delta < 0
    return TrendDirection.IMPROVING if improved else TrendDirection.DECLINING


def _count_trend(
    name: str,
    observations: Observations,
    categories: tuple[str, ...],
    higher_is_better: bool,
    unit: str,
) -> Trend:
    matching = tuple(
        event
        for event in observations.completed
        if _in_categories(event, categories)
    )
    if not matching or observations.window is None:
        return Trend(
            name,
            TrendDirection.INSUFFICIENT_DATA,
            0.0,
            0.0,
            f"No completed Events match {name}",
        )
    first, second = observations.split_halves(matching)
    return Trend(
        name=name,
        direction=_direction(
            len(first), len(second), higher_is_better, COUNT_TOLERANCE
        ),
        first_half=float(len(first)),
        second_half=float(len(second)),
        description=(
            f"{name}: {len(first)} -> {len(second)} {unit} across the "
            "analysis window"
        ),
    )


def _schedule_adherence(observations: Observations) -> Trend:
    def ratio(completed, skipped) -> float | None:
        total = len(completed) + len(skipped)
        return len(completed) / total if total else None

    if observations.window is None:
        return Trend(
            "Schedule adherence",
            TrendDirection.INSUFFICIENT_DATA,
            0.0,
            0.0,
            "No window",
        )
    completed_first, completed_second = observations.split_halves(
        observations.completed
    )
    skipped_first, skipped_second = observations.split_halves(
        observations.skipped
    )
    first = ratio(completed_first, skipped_first)
    second = ratio(completed_second, skipped_second)
    if first is None or second is None:
        return Trend(
            "Schedule adherence",
            TrendDirection.INSUFFICIENT_DATA,
            first or 0.0,
            second or 0.0,
            "Not enough terminal Events in both halves",
        )
    return Trend(
        name="Schedule adherence",
        direction=_direction(first, second, True, RATIO_TOLERANCE),
        first_half=round(first, 4),
        second_half=round(second, 4),
        description=(
            f"Completion ratio moved {first:.0%} -> {second:.0%}"
        ),
    )


def _study_consistency(observations: Observations) -> Trend:
    matching = tuple(
        event
        for event in observations.completed
        if _in_categories(event, STUDY_CATEGORIES)
    )
    if not matching or observations.window is None:
        return Trend(
            "Study consistency",
            TrendDirection.INSUFFICIENT_DATA,
            0.0,
            0.0,
            "No completed study Events",
        )
    first, second = observations.split_halves(matching)

    def distinct_days(events) -> int:
        return len(
            {
                anchor_time(event).date()
                for event in events
                if anchor_time(event) is not None
            }
        )

    first_days, second_days = distinct_days(first), distinct_days(second)
    return Trend(
        name="Study consistency",
        direction=_direction(first_days, second_days, True, COUNT_TOLERANCE),
        first_half=float(first_days),
        second_half=float(second_days),
        description=(
            f"Distinct study days: {first_days} -> {second_days}"
        ),
    )


def _finance_discipline(observations: Observations) -> Trend:
    def net_money(events) -> float:
        total = 0.0
        for event in events:
            total += event.resource_flow.produced.get(ResourceType.MONEY, 0.0)
            total -= event.resource_flow.consumed.get(ResourceType.MONEY, 0.0)
        return total

    money_events = tuple(
        event
        for event in observations.completed
        if ResourceType.MONEY in event.resource_flow.consumed
        or ResourceType.MONEY in event.resource_flow.produced
    )
    if not money_events or observations.window is None:
        return Trend(
            "Finance discipline",
            TrendDirection.INSUFFICIENT_DATA,
            0.0,
            0.0,
            "No Events with Money flows",
        )
    first, second = observations.split_halves(money_events)
    first_net, second_net = net_money(first), net_money(second)
    return Trend(
        name="Finance discipline",
        direction=_direction(first_net, second_net, True, RATIO_TOLERANCE),
        first_half=round(first_net, 2),
        second_half=round(second_net, 2),
        description=f"Net Money flow: {first_net:g} -> {second_net:g}",
    )


def _deep_work_quality(observations: Observations) -> Trend:
    matching = tuple(
        event
        for event in observations.completed
        if _in_categories(event, DEEP_WORK_CATEGORIES)
    )
    if not matching or observations.window is None:
        return Trend(
            "Deep work quality",
            TrendDirection.INSUFFICIENT_DATA,
            0.0,
            0.0,
            "No completed deep-work Events",
        )
    first, second = observations.split_halves(matching)

    def average_minutes(events) -> float:
        durations = [
            event.duration.minutes
            for event in events
            if event.duration is not None
        ]
        return sum(durations) / len(durations) if durations else 0.0

    first_avg, second_avg = average_minutes(first), average_minutes(second)
    return Trend(
        name="Deep work quality",
        direction=_direction(first_avg, second_avg, True, 1.0),
        first_half=round(first_avg, 1),
        second_half=round(second_avg, 1),
        description=(
            f"Average deep-work session: {first_avg:g} -> {second_avg:g} "
            "minutes"
        ),
    )


def _reflection_quality(history: History, observations: Observations) -> Trend:
    if observations.window is None or not observations.completed:
        return Trend(
            "Reflection coverage",
            TrendDirection.INSUFFICIENT_DATA,
            0.0,
            0.0,
            "No completed Events",
        )
    first, second = observations.split_halves(observations.completed)

    def coverage(events) -> float | None:
        if not events:
            return None
        reflected = sum(
            1 for event in events if event.reflection_id is not None
        )
        return reflected / len(events)

    first_cov, second_cov = coverage(first), coverage(second)
    if first_cov is None or second_cov is None:
        return Trend(
            "Reflection coverage",
            TrendDirection.INSUFFICIENT_DATA,
            first_cov or 0.0,
            second_cov or 0.0,
            "Not enough completed Events in both halves",
        )
    return Trend(
        name="Reflection coverage",
        direction=_direction(first_cov, second_cov, True, RATIO_TOLERANCE),
        first_half=round(first_cov, 4),
        second_half=round(second_cov, 4),
        description=(
            f"Completed Events with a Reflection: "
            f"{first_cov:.0%} -> {second_cov:.0%}"
        ),
    )


def analyze_trends(
    history: History, observations: Observations
) -> tuple[Trend, ...]:
    return (
        _schedule_adherence(observations),
        _study_consistency(observations),
        _count_trend(
            "Smoking", observations, SMOKING_CATEGORIES, False, "events"
        ),
        _count_trend(
            "Alcohol", observations, ALCOHOL_CATEGORIES, False, "events"
        ),
        _finance_discipline(observations),
        _deep_work_quality(observations),
        _reflection_quality(history, observations),
    )
