"""Candidate Habit Changes — proposals, never edits.

Implements the documented Domain Policies deterministically:
"Repeated Events infer Habits" and "a confidence threshold, once crossed,
creates Habit candidates" (BUSINESS_RULES.md - Domain Policies). The
learning layer only PROPOSES: reinforcement, weakening, or creation.
The Application decides whether to apply anything.
"""

from dataclasses import dataclass
from enum import Enum, unique

from paios.domain.enums import ImpactType
from paios.domain.value_objects.identifiers import HabitId
from paios.learning.analyzer import Finding, FindingKind
from paios.learning.extractor import Observations, category_of
from paios.learning.history import History

#: Domain-Policy constants (evolvable, documented).
HABIT_CANDIDATE_THRESHOLD = 3
HABIT_JUDGEMENT_THRESHOLD = 3


@unique
class HabitChangeAction(Enum):
    REINFORCE = "Reinforce"
    WEAKEN = "Weaken"
    CREATE = "Create"


@dataclass(frozen=True)
class CandidateHabitChange:
    action: HabitChangeAction
    name: str
    rationale: str
    evidence: tuple[str, ...]
    habit_id: HabitId | None = None


def _matching_events(observations: Observations, name: str):
    lowered = name.strip().lower()
    return tuple(
        event
        for event in observations.completed
        if category_of(event) == lowered or lowered in category_of(event)
    )


def propose_habit_changes(
    history: History,
    observations: Observations,
    findings: tuple[Finding, ...],
) -> tuple[CandidateHabitChange, ...]:
    proposals: list[CandidateHabitChange] = []
    misuse_categories = {
        finding.category
        for finding in findings
        if finding.kind is FindingKind.REWARD_MISUSE
    }

    # Existing habits: judge their recent evidence.
    for habit in sorted(history.habits, key=lambda h: str(h.habit_id)):
        events = _matching_events(observations, habit.name)
        if len(events) < HABIT_JUDGEMENT_THRESHOLD:
            continue
        opportunities = sum(
            1 for e in events if e.impact_type is ImpactType.OPPORTUNITY
        )
        distractions = sum(
            1 for e in events if e.impact_type is ImpactType.DISTRACTION
        )
        evidence = tuple(str(e.event_id) for e in events)
        misused = habit.name.strip().lower() in misuse_categories
        if distractions > opportunities or misused:
            proposals.append(
                CandidateHabitChange(
                    action=HabitChangeAction.WEAKEN,
                    name=habit.name,
                    habit_id=habit.habit_id,
                    rationale=(
                        f"{distractions} of {len(events)} matching Events "
                        "were Distractions"
                        + ("; its reward reinforces them" if misused else "")
                    ),
                    evidence=evidence,
                )
            )
        elif opportunities > distractions:
            proposals.append(
                CandidateHabitChange(
                    action=HabitChangeAction.REINFORCE,
                    name=habit.name,
                    habit_id=habit.habit_id,
                    rationale=(
                        f"{opportunities} of {len(events)} matching Events "
                        "were Opportunities"
                    ),
                    evidence=evidence,
                )
            )

    # New habit candidates: repeated completed Events with no habit yet.
    known = {habit.name.strip().lower() for habit in history.habits}
    by_category: dict[str, list] = {}
    for event in observations.completed:
        by_category.setdefault(category_of(event), []).append(event)
    for category in sorted(by_category):
        events = by_category[category]
        if len(events) < HABIT_CANDIDATE_THRESHOLD:
            continue
        if any(category == name or name in category for name in known):
            continue
        proposals.append(
            CandidateHabitChange(
                action=HabitChangeAction.CREATE,
                name=category,
                rationale=(
                    f"{len(events)} completed '{category}' Events with no "
                    "Habit tracking them (repeated Events infer Habits)"
                ),
                evidence=tuple(str(e.event_id) for e in events),
            )
        )
    return tuple(proposals)
