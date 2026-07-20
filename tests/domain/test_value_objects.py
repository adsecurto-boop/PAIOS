"""Value objects: identifiers, time, ResourceFlow, EventOutcome."""

from dataclasses import FrozenInstanceError
from datetime import timedelta

import pytest

from paios.domain.enums import EventOutcomeType, ResourceType
from paios.domain.errors import DomainValidationError
from paios.domain.value_objects.event_outcome import EventOutcome
from paios.domain.value_objects.identifiers import ContextWindowId, EventId, UserId
from paios.domain.value_objects.resource_flow import ResourceFlow
from paios.domain.value_objects.time import Duration, TimeRange

from tests.domain.conftest import T0, at


class TestIdentifiers:
    def test_equality_is_by_value(self):
        assert EventId("evt_001") == EventId("evt_001")
        assert EventId("evt_001") != EventId("evt_002")

    def test_different_identifier_types_are_never_equal(self):
        assert EventId("x") != UserId("x")

    def test_new_generates_unique_ids(self):
        assert EventId.new() != EventId.new()

    def test_empty_value_rejected(self):
        with pytest.raises(DomainValidationError):
            EventId("")
        with pytest.raises(DomainValidationError):
            ContextWindowId("   ")

    def test_immutable(self):
        event_id = EventId("evt_001")
        with pytest.raises(FrozenInstanceError):
            event_id.value = "evt_002"


class TestDuration:
    def test_minutes(self):
        assert Duration(120).minutes == 120

    def test_negative_rejected(self):
        with pytest.raises(DomainValidationError):
            Duration(-1)

    def test_non_integer_rejected(self):
        with pytest.raises(DomainValidationError):
            Duration(1.5)

    def test_between(self):
        assert Duration.between(T0, at(120)) == Duration(120)

    def test_between_rejects_reversed(self):
        with pytest.raises(DomainValidationError):
            Duration.between(at(10), T0)

    def test_timedelta_round_trip(self):
        assert Duration.from_timedelta(timedelta(hours=2)) == Duration(120)
        assert Duration(90).to_timedelta() == timedelta(minutes=90)


class TestTimeRange:
    def test_duration(self):
        assert TimeRange(T0, at(465)).duration == Duration(465)

    def test_end_before_start_rejected(self):
        with pytest.raises(DomainValidationError):
            TimeRange(at(10), T0)

    def test_contains(self):
        window = TimeRange(T0, at(60))
        assert window.contains(at(30))
        assert not window.contains(at(61))


class TestResourceFlow:
    def test_consumed_and_produced(self):
        flow = ResourceFlow(
            consumed={ResourceType.TIME: 120, ResourceType.ENERGY: 20},
            produced={ResourceType.KNOWLEDGE: 35, ResourceType.CAREER: 25},
        )
        assert flow.consumed[ResourceType.TIME] == 120
        assert flow.produced[ResourceType.KNOWLEDGE] == 35
        assert not flow.is_empty

    def test_empty(self):
        assert ResourceFlow.empty().is_empty

    def test_amounts_must_be_positive_magnitudes(self):
        with pytest.raises(DomainValidationError):
            ResourceFlow(consumed={ResourceType.ENERGY: -10})
        with pytest.raises(DomainValidationError):
            ResourceFlow(produced={ResourceType.KNOWLEDGE: 0})

    def test_keys_must_be_resource_types(self):
        with pytest.raises(DomainValidationError):
            ResourceFlow(consumed={"energy": 10})

    def test_mappings_are_immutable(self):
        flow = ResourceFlow(consumed={ResourceType.TIME: 120})
        with pytest.raises(TypeError):
            flow.consumed[ResourceType.TIME] = 999


class TestEventOutcome:
    def test_immutable_evidence(self):
        outcome = EventOutcome(EventOutcomeType.PARTIAL, T0, note="Stopped early")
        with pytest.raises(FrozenInstanceError):
            outcome.outcome_type = EventOutcomeType.COMPLETED
