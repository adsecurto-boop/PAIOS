"""Intent -> Recommendation building and PlanningService transforms (M20)."""

from datetime import datetime, timedelta

import pytest

from paios.domain.enums import RecommendationStatus
from paios.domain.value_objects.identifiers import UserId
from paios.planning.intents import (
    DEFAULT_VALIDITY,
    EventIntent,
    build_user_recommendation,
)
from paios.planning.service import PlanningService

T0 = datetime(2026, 7, 22, 9, 0)
USER = UserId("user_001")


class TestBuildUserRecommendation:
    def test_recommendation_is_born_generated_with_intent_facts(self):
        intent = EventIntent(
            user_id=USER,
            title="Buy medicine",
            suggested_time=T0 + timedelta(hours=8),
            priority=2.0,
        )
        recommendation = build_user_recommendation(intent, T0)
        assert recommendation.status is RecommendationStatus.GENERATED
        assert recommendation.reason == "Buy medicine"
        assert recommendation.suggested_timing == T0 + timedelta(hours=8)
        assert recommendation.priority == 2.0
        assert (
            recommendation.expires_at
            == T0 + timedelta(hours=8) + DEFAULT_VALIDITY
        )

    def test_identity_is_deterministic_content_hash(self):
        intent = EventIntent(user_id=USER, title="Gym")
        first = build_user_recommendation(intent, T0)
        second = build_user_recommendation(intent, T0)
        assert first.recommendation_id == second.recommendation_id
        different_moment = build_user_recommendation(
            intent, T0 + timedelta(minutes=1)
        )
        assert (
            different_moment.recommendation_id != first.recommendation_id
        )

    def test_namespace_disjoint_from_decision_engine(self):
        from paios.decision_engine.recommendation_builder import (
            _ID_NAMESPACE as ENGINE_NAMESPACE,
        )
        from paios.planning.intents import _ID_NAMESPACE

        assert _ID_NAMESPACE != ENGINE_NAMESPACE


class TestPlanningService:
    def test_instantiate_template_produces_intent_and_metadata(self, tmp_path):
        service = PlanningService(tmp_path)
        template = service.templates.add(
            "Gym", "Gym session", T0, metadata={"energy": "high"}
        )
        intent, metadata = service.instantiate_template(
            template["id"], USER, T0 + timedelta(days=1)
        )
        assert intent.title == "Gym session"
        assert intent.suggested_time == T0 + timedelta(days=1)
        assert metadata == {"energy": "high"}

    def test_recurrence_walk_hits_only_configured_weekdays(self, tmp_path):
        service = PlanningService(tmp_path)
        # 2026-07-22 is a Wednesday.
        rule = service.recurrences.add(
            "Temple", "07:30", ["sun"], T0, T0
        )
        next_run = service.next_occurrence(rule, T0)
        assert next_run == datetime(2026, 7, 26, 7, 30)  # Sunday
        following = service.next_occurrence(rule, next_run)
        assert following == datetime(2026, 8, 2, 7, 30)

    def test_due_and_expand_advances_next_run(self, tmp_path):
        service = PlanningService(tmp_path)
        rule = service.recurrences.add(
            "Temple", "07:30", ["wed", "sun"],
            datetime(2026, 7, 22, 7, 30), T0,
        )
        due = service.due_recurrences(T0)
        assert [item["id"] for item in due] == [rule["id"]]
        intent, metadata, next_run = service.expand_recurrence(
            due[0], USER, T0
        )
        assert intent.title == "Temple"
        assert intent.suggested_time == datetime(2026, 7, 22, 7, 30)
        assert next_run == datetime(2026, 7, 26, 7, 30)
        service.recurrences.set_next_run(rule["id"], next_run)
        assert service.due_recurrences(T0) == []

    def test_disabled_rule_never_due(self, tmp_path):
        service = PlanningService(tmp_path)
        rule = service.recurrences.add("X", "07:00", ["mon"], T0, T0)
        record = service.recurrences.get(rule["id"])
        record["enabled"] = False
        service.recurrences._put(rule["id"], record)
        assert service.due_recurrences(T0 + timedelta(days=30)) == []
