"""Deterministic expert rules — candidate generation (DECISION_ENGINE.md §4).

Each rule reads ONLY the RuntimeSnapshot and emits immutable Candidates.
Every concrete rule implements a candidate type from the documented
catalog (Continue Current Event, Resume Event, Recommend Rest, Recommend
Reflection, Recommend Learning, Recommend Focus Session, habit-consistent
actions) using the documented generation sources (Context, Resources,
Goals, Habits, Projects, Knowledge, Current Event).

Thresholds and base priorities are Domain-Policy constants — evolvable
runtime rules, deliberately visible, never Principles (BUSINESS_RULES.md).
All iteration is sorted for determinism.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from paios.domain.enums import (
    EventStatus,
    GoalStatus,
    PrincipleCategory,
    ProjectStatus,
    ResourceType,
)
from paios.domain.value_objects.identifiers import ProjectId, UserId
from paios.runtime.runtime_snapshot import RuntimeSnapshot

# --- Domain-Policy constants (evolvable, documented) ----------------------
LOW_ENERGY_THRESHOLD = 30.0
KNOWLEDGE_GAP_CONFIDENCE = 50.0
HABIT_REINFORCEMENT_STRENGTH = 40.0

PRIORITY_REST = 8.0
PRIORITY_RESUME = 7.0
PRIORITY_CONTINUE = 6.0
PRIORITY_FOCUS = 6.0
PRIORITY_LEARNING = 5.0
PRIORITY_REFLECTION = 4.0
PRIORITY_HABIT = 3.0

ENERGY_COST_LEARNING = 20.0
ENERGY_COST_FOCUS = 25.0


@dataclass(frozen=True)
class Candidate:
    """An immutable possible next action, fully traceable to its facts."""

    rule_id: str
    key: str  # unique within the rule; part of the deterministic ID
    action: str
    reason: str
    expected_benefit: str
    user_id: UserId
    base_priority: float
    category: str
    facts: tuple[str, ...] = ()
    aligned_principles: tuple[str, ...] = ()
    violates_principles: tuple[str, ...] = ()
    required_energy: float = 0.0
    related_project_id: ProjectId | None = None
    suggested_timing: datetime | None = None
    momentum: bool = False
    goal_aligned: bool = False
    knowledge_growth: bool = False
    habit_reinforcing: bool = False


class Rule(ABC):
    """One deterministic reasoning rule over the snapshot."""

    rule_id: str = ""

    @abstractmethod
    def evaluate(self, snapshot: RuntimeSnapshot) -> tuple[Candidate, ...]:
        """Return zero or more Candidates; must be pure and deterministic."""


def _principle_names(
    snapshot: RuntimeSnapshot, *categories: PrincipleCategory
) -> tuple[str, ...]:
    """The actual Principles (by name) in the given categories — so every
    explanation cites real Principles, never invented ones."""
    return tuple(
        principle.name
        for principle in sorted(
            snapshot.principles, key=lambda p: str(p.principle_id)
        )
        if principle.category in categories
    )


class ContinueRunningEventRule(Rule):
    """§4 'Continue Current Event': preserve momentum, avoid interruption."""

    rule_id = "continue-running-event"

    def evaluate(self, snapshot: RuntimeSnapshot) -> tuple[Candidate, ...]:
        event = snapshot.running_event
        if event is None:
            return ()
        facts = [f"Event {event.event_id} ({event.description}) is running"]
        if event.start_time is not None:
            facts.append(f"Running since {event.start_time.isoformat()}")
        return (
            Candidate(
                rule_id=self.rule_id,
                key=str(event.event_id),
                action="Continue the current Event",
                reason=f"Continue: {event.description}",
                expected_benefit="Preserves momentum and avoids interruption cost",
                user_id=event.user_id,
                base_priority=PRIORITY_CONTINUE,
                category=event.category,
                facts=tuple(facts),
                aligned_principles=_principle_names(
                    snapshot, PrincipleCategory.RESPONSIBILITY
                ),
                momentum=True,
            ),
        )


class ResumeSuspendedEventRule(Rule):
    """§4 'Resume Event': a Paused or Interrupted Event awaits continuation
    (an Interrupted Event still expects to resume — DOMAIN_MODEL P19)."""

    rule_id = "resume-suspended-event"

    def evaluate(self, snapshot: RuntimeSnapshot) -> tuple[Candidate, ...]:
        suspended = sorted(
            (
                event
                for event in snapshot.events
                if event.status
                in (EventStatus.PAUSED, EventStatus.INTERRUPTED)
            ),
            key=lambda event: str(event.event_id),
        )
        return tuple(
            Candidate(
                rule_id=self.rule_id,
                key=str(event.event_id),
                action="Resume the suspended Event",
                reason=f"Resume: {event.description}",
                expected_benefit="Completes partial work already invested in",
                user_id=event.user_id,
                base_priority=PRIORITY_RESUME,
                category=event.category,
                facts=(
                    f"Event {event.event_id} is {event.status.value}",
                    f"Description: {event.description}",
                ),
                aligned_principles=_principle_names(
                    snapshot, PrincipleCategory.RESPONSIBILITY
                ),
                momentum=True,
            )
            for event in suspended
        )


class RestRule(Rule):
    """§4 'Recommend Rest' / generation source 'From Resources':
    low Energy suggests rest; protects Health Principles."""

    rule_id = "rest-on-low-energy"

    def evaluate(self, snapshot: RuntimeSnapshot) -> tuple[Candidate, ...]:
        candidates = []
        for resource in sorted(
            snapshot.resources, key=lambda r: str(r.resource_id)
        ):
            if (
                resource.type is ResourceType.ENERGY
                and resource.current_value < LOW_ENERGY_THRESHOLD
            ):
                candidates.append(
                    Candidate(
                        rule_id=self.rule_id,
                        key=str(resource.resource_id),
                        action="Rest and recover",
                        reason=(
                            f"Energy is low ({resource.current_value:g} "
                            f"{resource.unit}); rest to recover"
                        ),
                        expected_benefit=(
                            "Restores Energy and enables sustained performance"
                        ),
                        user_id=resource.user_id,
                        base_priority=PRIORITY_REST,
                        category="rest",
                        facts=(
                            f"Energy resource at {resource.current_value:g} "
                            f"(threshold {LOW_ENERGY_THRESHOLD:g})",
                        ),
                        aligned_principles=_principle_names(
                            snapshot, PrincipleCategory.HEALTH
                        ),
                    )
                )
        return tuple(candidates)


class ReflectionRule(Rule):
    """§4 'Recommend Reflection': completed Events without a Reflection are
    unharvested learning."""

    rule_id = "reflect-on-completed"

    def evaluate(self, snapshot: RuntimeSnapshot) -> tuple[Candidate, ...]:
        unreflected = sorted(
            (
                event
                for event in snapshot.events
                if event.status is EventStatus.COMPLETED
                and event.reflection_id is None
            ),
            key=lambda event: str(event.event_id),
        )
        if not unreflected:
            return ()
        first = unreflected[0]
        return (
            Candidate(
                rule_id=self.rule_id,
                key=str(first.event_id),
                action="Reflect on a completed Event",
                reason=(
                    f"Reflect on: {first.description} "
                    f"({len(unreflected)} completed Event(s) lack a Reflection)"
                ),
                expected_benefit="Turns experience into reusable Insights",
                user_id=first.user_id,
                base_priority=PRIORITY_REFLECTION,
                category="reflection",
                facts=(
                    f"{len(unreflected)} completed Event(s) without Reflection",
                    f"Oldest by ID: {first.event_id}",
                ),
                aligned_principles=_principle_names(
                    snapshot, PrincipleCategory.LEARNING
                ),
                knowledge_growth=True,
            ),
        )


class LearningRule(Rule):
    """§4 'Recommend Learning' / source 'From Knowledge': the weakest
    Knowledge item is the clearest gap."""

    rule_id = "close-knowledge-gap"

    def evaluate(self, snapshot: RuntimeSnapshot) -> tuple[Candidate, ...]:
        gaps = sorted(
            (
                knowledge
                for knowledge in snapshot.knowledge
                if knowledge.confidence < KNOWLEDGE_GAP_CONFIDENCE
            ),
            key=lambda k: (k.confidence, str(k.knowledge_id)),
        )
        if not gaps:
            return ()
        weakest = gaps[0]
        return (
            Candidate(
                rule_id=self.rule_id,
                key=str(weakest.knowledge_id),
                action="Study the weakest Knowledge area",
                reason=(
                    f"Study {weakest.topic} — {weakest.concept} "
                    f"(confidence {weakest.confidence:g}/100)"
                ),
                expected_benefit="Closes the largest Knowledge gap",
                user_id=weakest.user_id,
                base_priority=PRIORITY_LEARNING,
                category="study",
                facts=(
                    f"Knowledge {weakest.knowledge_id} confidence "
                    f"{weakest.confidence:g} < {KNOWLEDGE_GAP_CONFIDENCE:g}",
                    f"Domain: {weakest.domain}, topic: {weakest.topic}",
                ),
                aligned_principles=_principle_names(
                    snapshot, PrincipleCategory.LEARNING
                ),
                required_energy=ENERGY_COST_LEARNING,
                related_project_id=weakest.project_id,
                knowledge_growth=True,
            ),
        )


class ProjectFocusRule(Rule):
    """§4 'Recommend Focus Session' / sources 'From Projects' and 'From
    Goals': the least-complete active Project deserves focused work; an
    accepted Goal referencing it makes the action goal-aligned."""

    rule_id = "focus-on-project"

    def evaluate(self, snapshot: RuntimeSnapshot) -> tuple[Candidate, ...]:
        progress_by_id = {
            str(progress.progress_id): progress for progress in snapshot.progress
        }
        active = []
        for project in sorted(
            snapshot.projects, key=lambda p: str(p.project_id)
        ):
            if project.status is not ProjectStatus.ACTIVE:
                continue
            progress = (
                progress_by_id.get(str(project.progress_id))
                if project.progress_id is not None
                else None
            )
            completion = (
                progress.completion_percentage if progress is not None else 0.0
            )
            if completion < 100.0:
                active.append((completion, project))
        if not active:
            return ()
        active.sort(key=lambda pair: (pair[0], str(pair[1].project_id)))
        completion, project = active[0]
        goal_aligned = any(
            goal.accepted_by_user
            and goal.status is GoalStatus.ACTIVE
            and project.project_id in goal.related_project_ids
            for goal in snapshot.goals
        )
        facts = [
            f"Project {project.name} is Active at {completion:g}% completion"
        ]
        principles = _principle_names(
            snapshot,
            PrincipleCategory.RESPONSIBILITY,
            PrincipleCategory.LEARNING,
        )
        if goal_aligned:
            facts.append("An accepted active Goal references this Project")
        return (
            Candidate(
                rule_id=self.rule_id,
                key=str(project.project_id),
                action="Focus session on the least-complete Project",
                reason=f"Focused work on project: {project.name}",
                expected_benefit="Advances intentional work toward completion",
                user_id=project.user_id,
                base_priority=PRIORITY_FOCUS,
                category="focus",
                facts=tuple(facts),
                aligned_principles=principles,
                required_energy=ENERGY_COST_FOCUS,
                related_project_id=project.project_id,
                goal_aligned=goal_aligned,
            ),
        )


class HabitReinforcementRule(Rule):
    """§4 source 'From Habits': reinforce the strongest beneficial pattern."""

    rule_id = "reinforce-habit"

    def evaluate(self, snapshot: RuntimeSnapshot) -> tuple[Candidate, ...]:
        strong = sorted(
            (
                habit
                for habit in snapshot.habits
                if habit.strength >= HABIT_REINFORCEMENT_STRENGTH
            ),
            key=lambda habit: (-habit.strength, str(habit.habit_id)),
        )
        if not strong:
            return ()
        habit = strong[0]
        return (
            Candidate(
                rule_id=self.rule_id,
                key=str(habit.habit_id),
                action="Reinforce an established Habit",
                reason=f"Keep the habit going: {habit.name}",
                expected_benefit="Strengthens an established positive pattern",
                user_id=habit.user_id,
                base_priority=PRIORITY_HABIT,
                category=habit.name,
                facts=(
                    f"Habit {habit.name} strength {habit.strength:g} "
                    f">= {HABIT_REINFORCEMENT_STRENGTH:g}",
                ),
                aligned_principles=_principle_names(
                    snapshot, PrincipleCategory.LEARNING
                ),
                habit_reinforcing=True,
            ),
        )


def default_rules() -> tuple[Rule, ...]:
    """The deterministic rule set, in fixed evaluation order."""
    return (
        ContinueRunningEventRule(),
        ResumeSuspendedEventRule(),
        RestRule(),
        ReflectionRule(),
        LearningRule(),
        ProjectFocusRule(),
        HabitReinforcementRule(),
    )
