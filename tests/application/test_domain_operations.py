"""Milestone 10 — Domain Operations through the Application facade.

Entity management is pure orchestration: domain constructors and aggregate
methods do the validating, repositories do the persisting. These tests
drive everything through the facade, then verify against the store.
"""

import pytest

from paios.application.exceptions import (
    ApplicationNotStartedError,
    DuplicateEntityError,
)
from paios.domain.entities.goal import Goal
from paios.domain.enums import (
    EventStatus,
    GoalStatus,
    PrincipleCategory,
    ProjectStatus,
    ResourceType,
)
from paios.domain.errors import (
    DomainError,
    DomainValidationError,
    ImmutabilityViolationError,
    InvariantViolationError,
)
from paios.domain.value_objects.identifiers import GoalId, KnowledgeId, UserId
from paios.repositories.errors import EntityNotFound

from tests.application.conftest import USER, at, seed_rest_scenario
from tests.application.test_use_cases import tick_and_get_rest_recommendation


def complete_one_event(application):
    """Drive the canonical loop until one Event is Completed."""
    recommendation = tick_and_get_rest_recommendation(application)
    application.accept_recommendation(recommendation.recommendation_id)
    event = application.components.kernel.runtime_state.events[0]
    application.start_event(event.event_id, at=at(5))
    application.complete_event(event.event_id, at=at(45))
    return event


class TestUserOperations:
    def test_add_and_list_and_get(self, started_app):
        user = started_app.add_user("Asha")
        assert [u.name for u in started_app.list_users()] == ["Asha"]
        assert started_app.get_user(user.user_id).name == "Asha"

    def test_duplicate_name_rejected(self, started_app):
        started_app.add_user("Asha")
        with pytest.raises(DuplicateEntityError, match="User"):
            started_app.add_user("Asha")

    def test_empty_name_rejected_by_domain(self, started_app):
        with pytest.raises(DomainValidationError):
            started_app.add_user("   ")


class TestGoalOperations:
    def test_user_created_goal_is_accepted_by_user(self, started_app):
        goal = started_app.add_goal(USER, "Learn Sanskrit", "Read fluently")
        assert goal.suggested_by == "User"
        assert goal.accepted_by_user is True
        assert goal.accepted_at is not None
        stored = started_app.components.repositories.goals().get(goal.goal_id)
        assert stored.name == "Learn Sanskrit"
        assert stored.accepted_by_user is True

    def test_duplicate_name_rejected(self, started_app):
        started_app.add_goal(USER, "Learn Sanskrit")
        with pytest.raises(DuplicateEntityError, match="Goal"):
            started_app.add_goal(USER, "Learn Sanskrit")

    def test_lifecycle_statuses(self, started_app):
        goal = started_app.add_goal(USER, "Learn Sanskrit")
        assert started_app.pause_goal(goal.goal_id).status is GoalStatus.PAUSED
        assert (
            started_app.resume_goal(goal.goal_id).status is GoalStatus.ACTIVE
        )
        assert (
            started_app.complete_goal(goal.goal_id).status
            is GoalStatus.COMPLETED
        )
        stored = started_app.components.repositories.goals().get(goal.goal_id)
        assert stored.status is GoalStatus.COMPLETED

    def test_accept_suggested_goal(self, app_builder):
        def seed(factory):
            seed_rest_scenario(factory)
            factory.goals().save(
                Goal(
                    goal_id=GoalId("goal_suggested"),
                    user_id=USER,
                    name="Exercise daily",
                    description="",
                )
            )

        application = app_builder(seed=seed)
        application.start()
        try:
            goal = application.get_goal(GoalId("goal_suggested"))
            assert goal.accepted_by_user is False
            accepted = application.accept_goal(GoalId("goal_suggested"))
            assert accepted.accepted_by_user is True
            stored = application.components.repositories.goals().get(
                GoalId("goal_suggested")
            )
            assert stored.accepted_by_user is True
        finally:
            application.stop()

    def test_unknown_goal_rejected(self, started_app):
        with pytest.raises(EntityNotFound):
            started_app.get_goal(GoalId("missing"))


class TestProjectOperations:
    def test_add_creates_and_attaches_progress(self, started_app):
        project = started_app.add_project(USER, "PAIOS", "Build it")
        assert project.progress_id is not None
        progress = started_app.get_project_progress(project.project_id)
        assert progress.project_id == project.project_id
        assert progress.completion_percentage == 0.0

    def test_progress_update_persists(self, started_app):
        project = started_app.add_project(USER, "PAIOS")
        started_app.update_project_progress(project.project_id, 40.0)
        stored = started_app.components.repositories.progress().get(
            project.progress_id
        )
        assert stored.completion_percentage == 40.0
        assert stored.last_updated is not None

    def test_progress_out_of_bounds_rejected_by_domain(self, started_app):
        project = started_app.add_project(USER, "PAIOS")
        with pytest.raises(DomainValidationError):
            started_app.update_project_progress(project.project_id, 150.0)

    def test_lifecycle_statuses(self, started_app):
        project = started_app.add_project(USER, "PAIOS")
        assert (
            started_app.pause_project(project.project_id).status
            is ProjectStatus.PAUSED
        )
        assert (
            started_app.resume_project(project.project_id).status
            is ProjectStatus.ACTIVE
        )
        assert (
            started_app.complete_project(project.project_id).status
            is ProjectStatus.COMPLETED
        )

    def test_duplicate_name_rejected(self, started_app):
        started_app.add_project(USER, "PAIOS")
        with pytest.raises(DuplicateEntityError, match="Project"):
            started_app.add_project(USER, "PAIOS")


class TestPrincipleOperations:
    def test_add_and_review(self, started_app):
        principle = started_app.add_principle(
            "Truth first", PrincipleCategory.TRUTH, "Never self-deceive"
        )
        assert principle.last_reviewed is None
        reviewed = started_app.review_principle(principle.principle_id)
        assert reviewed.last_reviewed is not None
        assert reviewed.name == "Truth first"  # nothing else changes
        stored = started_app.components.repositories.principles().get(
            principle.principle_id
        )
        assert stored.last_reviewed == reviewed.last_reviewed

    def test_duplicate_name_rejected(self, started_app):
        started_app.add_principle("Truth first", PrincipleCategory.TRUTH)
        with pytest.raises(DuplicateEntityError, match="Principle"):
            started_app.add_principle("Truth first", PrincipleCategory.HEALTH)


class TestResourceOperations:
    def test_add_consume_produce(self, started_app):
        resource = started_app.add_resource(
            USER, ResourceType.FOCUS, 50.0, "points"
        )
        assert (
            started_app.consume_resource(
                resource.resource_id, 20.0
            ).current_value
            == 30.0
        )
        assert (
            started_app.produce_resource(
                resource.resource_id, 5.0
            ).current_value
            == 35.0
        )
        stored = started_app.components.repositories.resources().get(
            resource.resource_id
        )
        assert stored.current_value == 35.0

    def test_over_consumption_violates_invariant(self, started_app):
        resource = started_app.add_resource(
            USER, ResourceType.FOCUS, 10.0, "points"
        )
        with pytest.raises(InvariantViolationError):
            started_app.consume_resource(resource.resource_id, 25.0)

    def test_non_positive_amount_rejected_by_domain(self, started_app):
        resource = started_app.add_resource(
            USER, ResourceType.FOCUS, 10.0, "points"
        )
        with pytest.raises(DomainValidationError):
            started_app.produce_resource(resource.resource_id, -1.0)

    def test_duplicate_user_and_type_rejected(self, started_app):
        # The seeded rest scenario already holds user_001's ENERGY resource.
        with pytest.raises(DuplicateEntityError, match="Resource"):
            started_app.add_resource(USER, ResourceType.ENERGY, 5.0, "points")


class TestContextOperations:
    def test_add_with_all_fields(self, started_app):
        context = started_app.add_context(
            "Deep Work",
            location="Library",
            people=("Asha", "Ravi"),
            emotion="calm",
            trigger="morning",
            reason="focus block",
            environment="quiet",
            notes="phone off",
        )
        stored = started_app.components.repositories.contexts().get(
            context.context_id
        )
        assert stored.location == "Library"
        assert stored.people == ("Asha", "Ravi")

    def test_duplicate_name_rejected(self, started_app):
        # "Office" is seeded by the rest scenario.
        with pytest.raises(DuplicateEntityError, match="Context"):
            started_app.add_context("Office")


class TestKnowledgeOperations:
    def test_add_revise_apply(self, started_app):
        knowledge = started_app.add_knowledge(
            USER, "Programming", "Python", "Dataclasses", confidence=30.0
        )
        revised = started_app.revise_knowledge(
            knowledge.knowledge_id, confidence=60.0
        )
        assert revised.revision_count == 1
        assert revised.confidence == 60.0
        applied = started_app.apply_knowledge(knowledge.knowledge_id)
        assert applied.applied is True
        stored = started_app.components.repositories.knowledge().get(
            knowledge.knowledge_id
        )
        assert stored.revision_count == 1
        assert stored.applied is True

    def test_confidence_out_of_bounds_rejected_by_domain(self, started_app):
        with pytest.raises(DomainValidationError):
            started_app.add_knowledge(
                USER, "Programming", "Python", "Dataclasses", confidence=150.0
            )

    def test_duplicate_concept_rejected(self, started_app):
        started_app.add_knowledge(USER, "Programming", "Python", "Dataclasses")
        with pytest.raises(DuplicateEntityError, match="Knowledge"):
            started_app.add_knowledge(
                USER, "Programming", "Python", "Dataclasses"
            )

    def test_unknown_knowledge_rejected(self, started_app):
        with pytest.raises(EntityNotFound):
            started_app.revise_knowledge(KnowledgeId("missing"))


class TestReflectionOperations:
    def test_reflection_on_completed_event_links_both_ways(self, started_app):
        event = complete_one_event(started_app)
        reflection = started_app.add_reflection(
            event.event_id,
            facts="Rested 40 minutes",
            lesson_learned="Short rest restores focus",
            confidence=0.8,
        )
        assert reflection.event_id == event.event_id
        assert reflection.context_window_id == event.context_window_id
        stored_event = started_app.components.repositories.events().get(
            event.event_id
        )
        assert stored_event.reflection_id == reflection.reflection_id
        stored = started_app.components.repositories.reflections().get(
            reflection.reflection_id
        )
        assert stored.lesson_learned == "Short rest restores focus"

    def test_second_reflection_rejected_as_immutable(self, started_app):
        event = complete_one_event(started_app)
        started_app.add_reflection(event.event_id, facts="First")
        with pytest.raises(ImmutabilityViolationError):
            started_app.add_reflection(event.event_id, facts="Second")

    def test_reflection_requires_completed_event(self, started_app):
        recommendation = tick_and_get_rest_recommendation(started_app)
        started_app.accept_recommendation(recommendation.recommendation_id)
        event = started_app.components.kernel.runtime_state.events[0]
        with pytest.raises(DomainValidationError):
            started_app.add_reflection(event.event_id, facts="Too early")
        assert started_app.list_reflections() == []  # store untouched

    def test_reflection_on_unknown_event_rejected(self, started_app):
        from paios.domain.value_objects.identifiers import EventId

        with pytest.raises(EntityNotFound):
            started_app.add_reflection(EventId("missing"))


class TestArchiveBehavior:
    def test_completed_event_archives_and_stays_immutable(self, started_app):
        event = complete_one_event(started_app)
        started_app.archive_event(event.event_id, at=at(60))
        stored = started_app.components.repositories.events().get(
            event.event_id
        )
        assert stored.status is EventStatus.ARCHIVED
        # Never mutate archived entities: no transition may leave Archived.
        with pytest.raises(DomainError):
            started_app.start_event(event.event_id, at=at(61))

    def test_archived_event_still_accepts_reflection_evidence(
        self, started_app
    ):
        event = complete_one_event(started_app)
        started_app.archive_event(event.event_id, at=at(60))
        reflection = started_app.add_reflection(
            event.event_id, lesson_learned="Evidence, not mutation"
        )
        stored = started_app.components.repositories.events().get(
            event.event_id
        )
        assert stored.reflection_id == reflection.reflection_id


class TestReadOnlyAggregates:
    def test_habits_and_insights_are_listable_but_not_creatable(
        self, started_app
    ):
        assert started_app.list_habits() == []
        assert started_app.list_insights() == []
        assert not hasattr(started_app, "add_habit")
        assert not hasattr(started_app, "add_insight")
        operations = started_app.components.operations
        assert not hasattr(operations, "add_habit")
        assert not hasattr(operations, "add_insight")


class TestRestartPersistence:
    def test_every_managed_aggregate_survives_restart(self, app_builder):
        application = app_builder(seed=seed_rest_scenario)
        application.start()
        user = application.add_user("Asha")
        goal = application.add_goal(user.user_id, "Learn Sanskrit")
        project = application.add_project(user.user_id, "PAIOS")
        principle = application.add_principle(
            "Truth first", PrincipleCategory.TRUTH
        )
        resource = application.add_resource(
            user.user_id, ResourceType.FOCUS, 50.0, "points"
        )
        context = application.add_context("Deep Work", location="Library")
        knowledge = application.add_knowledge(
            user.user_id, "Programming", "Python", "Dataclasses"
        )
        application.update_project_progress(project.project_id, 25.0)
        application.stop()

        reborn = app_builder()
        reborn.start()
        try:
            assert reborn.get_user(user.user_id).name == "Asha"
            assert reborn.get_goal(goal.goal_id).accepted_by_user is True
            assert (
                reborn.get_project_progress(
                    project.project_id
                ).completion_percentage
                == 25.0
            )
            assert (
                reborn.get_principle(principle.principle_id).category
                is PrincipleCategory.TRUTH
            )
            assert reborn.get_resource(resource.resource_id).unit == "points"
            assert reborn.get_context(context.context_id).location == "Library"
            assert (
                reborn.get_knowledge(knowledge.knowledge_id).concept
                == "Dataclasses"
            )
            # The rebooted kernel loads the new aggregates into Runtime State.
            counts = reborn.status().aggregate_counts
            assert counts["users"] == 1
            assert counts["goals"] == 1
            assert counts["projects"] == 1
        finally:
            reborn.stop()


class TestLifecycleGuards:
    def test_operations_require_a_started_application(self, app_builder):
        application = app_builder(seed=seed_rest_scenario)
        with pytest.raises(ApplicationNotStartedError):
            application.add_user("Asha")
        with pytest.raises(ApplicationNotStartedError):
            application.list_goals()
