"""Candidate Principles — suggestions for the User, never edits.

Principles are immutable Dharma and never evolve (DOMAIN_MODEL.md
Principle 1); only the User may deliberately create or change one. The
learning layer therefore emits CANDIDATE value objects derived from
strong recurring evidence, skipping anything an existing Principle
already names.
"""

from dataclasses import dataclass

from paios.domain.enums import PrincipleCategory, ResourceType
from paios.learning.analyzer import (
    Finding,
    FindingKind,
    REPEAT_THRESHOLD,
    SMOKING_CATEGORIES,
    ALCOHOL_CATEGORIES,
    STUDY_CATEGORIES,
)
from paios.learning.extractor import Observations, category_of
from paios.learning.history import History


@dataclass(frozen=True)
class CandidatePrinciple:
    name: str
    description: str
    category: PrincipleCategory
    rationale: str
    evidence: tuple[str, ...]


def _existing_names(history: History) -> set[str]:
    return {principle.name.strip().lower() for principle in history.principles}


def propose_principles(
    history: History,
    observations: Observations,
    findings: tuple[Finding, ...],
) -> tuple[CandidatePrinciple, ...]:
    proposals: list[CandidatePrinciple] = []
    existing = _existing_names(history)

    def add(candidate: CandidatePrinciple) -> None:
        if candidate.name.strip().lower() not in existing:
            proposals.append(candidate)

    # Health: recurring harmful-substance Events.
    for label, names in (("Smoking", SMOKING_CATEGORIES),
                         ("Alcohol", ALCOHOL_CATEGORIES)):
        events = tuple(
            event
            for event in observations.completed
            if any(name in category_of(event) for name in names)
        )
        if len(events) >= REPEAT_THRESHOLD:
            add(
                CandidatePrinciple(
                    name=f"Reduce {label}",
                    description=(
                        f"Treat every {label.lower()} occasion as a "
                        "deliberate exception, not a default"
                    ),
                    category=PrincipleCategory.HEALTH,
                    rationale=(
                        f"{len(events)} completed {label.lower()} Events "
                        "in the analysis window"
                    ),
                    evidence=tuple(str(e.event_id) for e in events),
                )
            )

    # Resources: net Money loss across the window.
    net = 0.0
    money_events = []
    for event in observations.completed:
        consumed = event.resource_flow.consumed.get(ResourceType.MONEY, 0.0)
        produced = event.resource_flow.produced.get(ResourceType.MONEY, 0.0)
        if consumed or produced:
            money_events.append(event)
            net += produced - consumed
    if len(money_events) >= REPEAT_THRESHOLD and net < 0:
        add(
            CandidatePrinciple(
                name="Guard Spending",
                description="Review every discretionary expense before it",
                category=PrincipleCategory.RESOURCES,
                rationale=(
                    f"Net Money flow across {len(money_events)} Events "
                    f"is {net:g}"
                ),
                evidence=tuple(str(e.event_id) for e in money_events),
            )
        )

    # Learning: repeated failures in study-like categories.
    for finding in findings:
        if finding.kind is not FindingKind.REPEATED_FAILURE:
            continue
        if any(name in finding.category for name in STUDY_CATEGORIES):
            add(
                CandidatePrinciple(
                    name="Prepare Before Studying",
                    description=(
                        "Enter every study session with a defined goal and "
                        "the material at hand"
                    ),
                    category=PrincipleCategory.LEARNING,
                    rationale=finding.description,
                    evidence=finding.evidence,
                )
            )
    return tuple(proposals)
