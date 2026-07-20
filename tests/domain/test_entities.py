"""Remaining entities: Principle, Context, User, Project, Progress,
Resource, Knowledge, Reflection, Insight, Habit, Goal."""

from dataclasses import FrozenInstanceError, fields

import pytest

from paios.domain.entities.context import Context
from paios.domain.entities.goal import Goal
from paios.domain.entities.habit import Habit
from paios.domain.entities.insight import Insight
from paios.domain.entities.knowledge import Knowledge
from paios.domain.entities.principle import Principle
from paios.domain.entities.progress import Progress
from paios.domain.entities.project import Project
from paios.domain.entities.reflection import Reflection
from paios.domain.entities.resource import Resource
from paios.domain.entities.user import User
from paios.domain.enums import (
    GoalStatus,
    PrincipleCategory,
    ProjectStatus,
    ResourceType,
)
from paios.domain.errors import DomainValidationError, InvariantViolationError
from paios.domain.value_objects.identifiers import (
    ContextId,
    ContextWindowId,
    EventId,
    GoalId,
    HabitId,
    InsightId,
    KnowledgeId,
    PrincipleId,
    ProgressId,
    ProjectId,
    ReflectionId,
    ResourceId,
    UserId,
)

from tests.domain.conftest import T0, at

USER = UserId("user_001")


class TestPrinciple:
    def make(self) -> Principle:
        return Principle(
            principle_id=PrincipleId("prin_001"),
            name="Protect Health",
            description="Prioritize actions that maintain health",
            category=PrincipleCategory.HEALTH,
            created_at=T0,
        )

    def test_immutable(self):
        principle = self.make()
        with pytest.raises(FrozenInstanceError):
            principle.name = "Altered"

    def test_review_produces_new_value_without_altering_original(self):
        principle = self.make()
        reviewed = principle.reviewed(at(10))
        assert principle.last_reviewed is None
        assert reviewed.last_reviewed == at(10)
        assert reviewed.name == principle.name

    def test_unowned_no_user_reference(self):
        assert "user_id" not in {field.name for field in fields(Principle)}


class TestContext:
    def test_static_and_immutable(self):
        context = Context(
            context_id=ContextId("ctx_001"),
            name="Office",
            created_at=T0,
            location="Downtown office, 4th floor",
            people=("Team Lead", "colleagues"),
            environment="Open workspace",
        )
        with pytest.raises(FrozenInstanceError):
            context.name = "Home"

    def test_carries_no_time_boundaries(self):
        field_names = {field.name for field in fields(Context)}
        assert "start_time" not in field_names
        assert "end_time" not in field_names

    def test_unowned_no_user_or_event_reference(self):
        field_names = {field.name for field in fields(Context)}
        assert "user_id" not in field_names
        assert "event_id" not in field_names


class TestUser:
    def test_activity_tracking(self):
        user = User(user_id=USER, name="Test User", created_at=T0)
        user.record_activity(at(5))
        assert user.last_active == at(5)


class TestProject:
    def make(self) -> Project:
        return Project(
            project_id=ProjectId("proj_001"),
            user_id=USER,
            name="ISTQB Certification",
            description="Complete ISTQB Foundation Level",
            created_at=T0,
        )

    def test_defaults_active(self):
        assert self.make().status is ProjectStatus.ACTIVE

    def test_owns_at_most_one_progress(self):
        project = self.make()
        project.attach_progress(ProgressId("prog_001"))
        project.attach_progress(ProgressId("prog_001"))
        with pytest.raises(DomainValidationError):
            project.attach_progress(ProgressId("prog_002"))


class TestProgress:
    def make(self) -> Progress:
        return Progress(
            progress_id=ProgressId("prog_001"), project_id=ProjectId("proj_001")
        )

    def test_completion_bounds(self):
        progress = self.make()
        progress.update(at(1), completion_percentage=45.0)
        assert progress.completion_percentage == 45.0
        assert progress.last_updated == at(1)
        with pytest.raises(DomainValidationError):
            progress.update(at(2), completion_percentage=101.0)


class TestResource:
    def make(self, value: float = 100.0, negative_allowed: bool = False) -> Resource:
        return Resource(
            resource_id=ResourceId("res_001"),
            user_id=USER,
            type=ResourceType.ENERGY,
            current_value=value,
            unit="points",
            negative_allowed=negative_allowed,
        )

    def test_consume_and_produce(self):
        resource = self.make(100.0)
        resource.consume(30.0, at(1))
        resource.produce(10.0, at(2))
        assert resource.current_value == 80.0
        assert resource.last_updated == at(2)

    def test_cannot_become_invalid(self):
        resource = self.make(10.0)
        with pytest.raises(InvariantViolationError):
            resource.consume(20.0, at(1))
        assert resource.current_value == 10.0

    def test_negative_allowed_where_meaningful(self):
        resource = self.make(10.0, negative_allowed=True)
        resource.consume(20.0, at(1))
        assert resource.current_value == -10.0

    def test_amounts_must_be_positive(self):
        with pytest.raises(DomainValidationError):
            self.make().consume(-5.0, at(1))
        with pytest.raises(DomainValidationError):
            self.make().produce(0.0, at(1))


class TestKnowledge:
    def make(self) -> Knowledge:
        return Knowledge(
            knowledge_id=KnowledgeId("kno_001"),
            user_id=USER,
            domain="Testing",
            topic="ISTQB",
            concept="Test Management",
        )

    def test_revision_tracking(self):
        knowledge = self.make()
        knowledge.revise(at(1), confidence=60.0)
        knowledge.revise(at(2))
        assert knowledge.revision_count == 2
        assert knowledge.last_revision == at(2)
        assert knowledge.confidence == 60.0

    def test_confidence_bounds(self):
        with pytest.raises(DomainValidationError):
            self.make().revise(at(1), confidence=101.0)


class TestReflection:
    def test_requires_event_and_window(self):
        reflection = Reflection(
            reflection_id=ReflectionId("ref_001"),
            event_id=EventId("evt_001"),
            context_window_id=ContextWindowId("win_001"),
            created_at=T0,
            lesson_learned="Morning study sessions are more effective",
        )
        with pytest.raises(FrozenInstanceError):
            reflection.lesson_learned = "rewritten"

    def test_cannot_exist_without_event(self):
        with pytest.raises((TypeError, DomainValidationError)):
            Reflection(
                reflection_id=ReflectionId("ref_001"),
                event_id=None,
                context_window_id=ContextWindowId("win_001"),
                created_at=T0,
            )


class TestInsight:
    def test_originates_from_reflection_and_is_immutable(self):
        insight = Insight(
            insight_id=InsightId("ins_001"),
            source_reflection_id=ReflectionId("ref_001"),
            created_at=T0,
            reusable=True,
        )
        with pytest.raises(FrozenInstanceError):
            insight.reusable = False


class TestHabit:
    def test_inferred_creation_path(self):
        habit = Habit.infer(
            habit_id=HabitId("hab_001"),
            user_id=USER,
            name="Morning Study",
            detected_at=T0,
            strength=40.0,
        )
        habit.update_strength(55.0, at(1))
        assert habit.strength == 55.0

    def test_strength_bounds(self):
        habit = Habit.infer(
            habit_id=HabitId("hab_001"),
            user_id=USER,
            name="Morning Study",
            detected_at=T0,
        )
        with pytest.raises(DomainValidationError):
            habit.update_strength(101.0, at(1))

    def test_never_owns_events(self):
        field_names = {field.name for field in fields(Habit)}
        assert not any("event" in name for name in field_names)


class TestGoal:
    def test_suggested_then_accepted_by_user(self):
        goal = Goal(
            goal_id=GoalId("goal_001"),
            user_id=USER,
            name="Continue towards SDET",
            description="Emergent direction from ISTQB project history",
        )
        assert goal.suggested_by == "Decision Engine"
        assert not goal.accepted_by_user
        goal.accept(at(1))
        assert goal.accepted_by_user
        assert goal.accepted_at == at(1)
        assert goal.status is GoalStatus.ACTIVE
