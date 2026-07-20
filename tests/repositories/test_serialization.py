"""Lossless serialization round-trips for every aggregate and value object."""

import pytest

from paios.domain.enums import (
    ContextWindowState,
    DisturberResolutionStatus,
    DisturberState,
    EventOutcomeType,
    EventStatus,
    ImpactType,
    RecommendationStatus,
    ResourceType,
)
from paios.domain.errors import ImmutabilityViolationError
from paios.domain.value_objects.time import Duration, TimeRange
from paios.repositories.errors import SerializationError
from paios.repositories.serialization import (
    deserialize_context,
    deserialize_context_window,
    deserialize_event,
    deserialize_event_disturber,
    deserialize_goal,
    deserialize_habit,
    deserialize_insight,
    deserialize_knowledge,
    deserialize_principle,
    deserialize_progress,
    deserialize_project,
    deserialize_recommendation,
    deserialize_reflection,
    deserialize_resource,
    deserialize_user,
    serialize_context,
    serialize_context_window,
    serialize_event,
    serialize_event_disturber,
    serialize_goal,
    serialize_habit,
    serialize_insight,
    serialize_knowledge,
    serialize_principle,
    serialize_progress,
    serialize_project,
    serialize_recommendation,
    serialize_reflection,
    serialize_resource,
    serialize_user,
)
from paios.repositories.serialization.primitives import (
    parse_time_range,
    serialize_time_range,
)

from tests.repositories.conftest import (
    T0,
    at,
    build_archived_disturber,
    build_completed_event,
    build_consumed_recommendation,
    build_context,
    build_expired_window,
    build_goal,
    build_habit,
    build_insight,
    build_knowledge,
    build_principle,
    build_progress,
    build_project,
    build_reflection,
    build_resource,
    build_user,
)

ROUND_TRIPS = [
    (build_user, serialize_user, deserialize_user),
    (build_principle, serialize_principle, deserialize_principle),
    (build_context, serialize_context, deserialize_context),
    (build_expired_window, serialize_context_window, deserialize_context_window),
    (build_completed_event, serialize_event, deserialize_event),
    (build_project, serialize_project, deserialize_project),
    (build_progress, serialize_progress, deserialize_progress),
    (build_resource, serialize_resource, deserialize_resource),
    (build_knowledge, serialize_knowledge, deserialize_knowledge),
    (
        build_consumed_recommendation,
        serialize_recommendation,
        deserialize_recommendation,
    ),
    (
        build_archived_disturber,
        serialize_event_disturber,
        deserialize_event_disturber,
    ),
    (build_reflection, serialize_reflection, deserialize_reflection),
    (build_insight, serialize_insight, deserialize_insight),
    (build_habit, serialize_habit, deserialize_habit),
    (build_goal, serialize_goal, deserialize_goal),
]


class TestRoundTrips:
    @pytest.mark.parametrize(
        "build, serialize, deserialize",
        ROUND_TRIPS,
        ids=[build.__name__ for build, _, _ in ROUND_TRIPS],
    )
    def test_lossless_roundtrip(self, build, serialize, deserialize):
        original = build()
        data = serialize(original)
        loaded = deserialize(data)
        assert serialize(loaded) == data


class TestEventFidelity:
    def test_full_state_and_value_objects_restored(self):
        event = deserialize_event(serialize_event(build_completed_event()))
        assert event.status is EventStatus.COMPLETED
        assert event.impact_type is ImpactType.OPPORTUNITY
        assert isinstance(event.duration, Duration)
        assert event.duration == Duration(120)
        assert event.resource_flow.consumed[ResourceType.TIME] == 120
        assert event.resource_flow.produced[ResourceType.KNOWLEDGE] == 35
        assert event.outcome.outcome_type is EventOutcomeType.COMPLETED
        assert event.outcome.note == "as planned"
        assert str(event.reflection_id) == "ref_001"

    def test_transition_history_order_and_evidence_preserved(self):
        original = build_completed_event()
        loaded = deserialize_event(serialize_event(original))
        assert len(loaded.transitions) == 7
        assert [r.to_state for r in loaded.transitions] == [
            r.to_state for r in original.transitions
        ]
        assert loaded.transitions[0].reason == "accepted"
        assert loaded.transitions[3].reason == "emergency call"
        assert all(r.actor == "Scheduler" for r in loaded.transitions)
        assert [r.occurred_at for r in loaded.transitions] == [
            r.occurred_at for r in original.transitions
        ]

    def test_loaded_event_still_enforces_immutability(self):
        loaded = deserialize_event(serialize_event(build_completed_event()))
        with pytest.raises(ImmutabilityViolationError):
            loaded.description = "rewritten history"

    def test_loaded_history_remains_append_only(self):
        loaded = deserialize_event(serialize_event(build_completed_event()))
        record = loaded.transition_to(EventStatus.ARCHIVED, at(500))
        assert record.from_state is EventStatus.COMPLETED
        assert len(loaded.transitions) == 8


class TestOtherLifecycleFidelity:
    def test_context_window_state_and_facts(self):
        loaded = deserialize_context_window(
            serialize_context_window(build_expired_window())
        )
        assert loaded.current_state is ContextWindowState.EXPIRED
        assert loaded.duration == Duration(65)
        assert loaded.reason_started == "Arrived at office"
        assert loaded.reason_ended == "Replacement window active"
        assert [r.to_state for r in loaded.transitions] == [
            ContextWindowState.ACTIVE,
            ContextWindowState.CHANGING,
            ContextWindowState.EXPIRED,
        ]

    def test_recommendation_status_and_evidence(self):
        loaded = deserialize_recommendation(
            serialize_recommendation(build_consumed_recommendation())
        )
        assert loaded.status is RecommendationStatus.CONSUMED
        assert loaded.transitions[1].reason == "user accepted"
        assert loaded.expires_at == at(120)

    def test_disturber_state_and_references(self):
        loaded = deserialize_event_disturber(
            serialize_event_disturber(build_archived_disturber())
        )
        assert loaded.state is DisturberState.ARCHIVED
        assert loaded.resolution_status is DisturberResolutionStatus.RESOLVED
        assert str(loaded.resulting_context_window_id) == "win_002"
        assert [str(i) for i in loaded.affected_scheduled_event_ids] == [
            "evt_003",
            "evt_004",
        ]

    def test_context_people_tuple_restored(self):
        loaded = deserialize_context(serialize_context(build_context()))
        assert loaded.people == ("Team Lead", "colleagues")
        assert isinstance(loaded.people, tuple)


class TestPrimitives:
    def test_time_range_roundtrip(self):
        original = TimeRange(T0, at(465))
        assert parse_time_range(serialize_time_range(original)) == original

    def test_time_range_none_passthrough(self):
        assert serialize_time_range(None) is None
        assert parse_time_range(None) is None


class TestCorruptionDetection:
    def test_invalid_enum_value_raises(self):
        data = serialize_event(build_completed_event())
        data["impact_type"] = "SuperOpportunity"
        with pytest.raises(SerializationError):
            deserialize_event(data)

    def test_missing_required_field_raises(self):
        data = serialize_event(build_completed_event())
        del data["category"]
        with pytest.raises(SerializationError):
            deserialize_event(data)

    def test_illegal_transition_sequence_raises(self):
        data = serialize_event(build_completed_event())
        data["transitions"] = [
            {
                "from_state": "Recommended",
                "to_state": "Completed",
                "occurred_at": T0.isoformat(),
                "actor": "Scheduler",
                "reason": None,
            }
        ]
        with pytest.raises(SerializationError):
            deserialize_event(data)

    def test_tampered_from_state_raises(self):
        data = serialize_event(build_completed_event())
        data["transitions"][1]["from_state"] = "Recommended"
        with pytest.raises(SerializationError, match="from_state"):
            deserialize_event(data)

    def test_stored_status_mismatch_raises(self):
        data = serialize_event(build_completed_event())
        data["status"] = "Started"
        with pytest.raises(SerializationError, match="does not match"):
            deserialize_event(data)

    def test_applied_disturber_without_window_reference_raises(self):
        data = serialize_event_disturber(build_archived_disturber())
        data["resulting_context_window_id"] = None
        with pytest.raises(SerializationError):
            deserialize_event_disturber(data)

    def test_invalid_datetime_raises(self):
        data = serialize_user(build_user())
        data["created_at"] = "yesterday-ish"
        with pytest.raises(SerializationError):
            deserialize_user(data)
