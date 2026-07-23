"""Serialization primitives: value objects, enums, datetimes, transitions.

Conventions (matching the ENTITY_RELATIONSHIPS.md storage examples):
- identifiers -> their string value
- enums -> their human-readable ``.value``
- datetime -> ISO 8601 string (lossless via ``datetime.fromisoformat``)
- Duration -> integer minutes
- TimeRange -> {"start": iso, "end": iso}
- ResourceFlow -> {"consumed": {type: amount}, "produced": {type: amount}}
- EventOutcome -> {"outcome_type", "recorded_at", "note"}
- TransitionRecord -> {"from_state", "to_state", "occurred_at", "actor",
  "reason"}
- ``None`` passes through as JSON null on both sides
"""

from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from typing import Iterator, Type, TypeVar

from paios.domain.enums import EventOutcomeType, ResourceType
from paios.domain.errors import DomainError
from paios.domain.state_machines.machine import TransitionRecord
from paios.domain.value_objects.event_outcome import EventOutcome
from paios.domain.value_objects.identifiers import Identifier
from paios.domain.value_objects.resource_flow import ResourceFlow
from paios.domain.value_objects.time import Duration, TimeRange
from paios.repositories.errors import SerializationError

E = TypeVar("E", bound=Enum)
I = TypeVar("I", bound=Identifier)


@contextmanager
def deserialization_guard(kind: str) -> Iterator[None]:
    """Report any structural or domain-level failure as SerializationError.

    Domain errors raised while replaying persisted data mean the stored
    record describes something the domain forbids — i.e. corrupted data.
    """
    try:
        yield
    except SerializationError:
        raise
    except (KeyError, ValueError, TypeError, AttributeError, DomainError) as exc:
        raise SerializationError(f"Cannot deserialize {kind}: {exc}") from exc


# --- datetime -------------------------------------------------------------


def serialize_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SerializationError(f"Expected ISO datetime string, got {value!r}")
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise SerializationError(f"Invalid ISO datetime {value!r}") from exc


# --- enums and identifiers ------------------------------------------------


def serialize_enum(value: Enum | None) -> str | None:
    return value.value if value is not None else None


def parse_enum(enum_cls: Type[E], value: str | None) -> E | None:
    if value is None:
        return None
    try:
        return enum_cls(value)
    except ValueError as exc:
        raise SerializationError(
            f"Invalid {enum_cls.__name__} value {value!r}"
        ) from exc


def serialize_id(value: Identifier | None) -> str | None:
    return value.value if value is not None else None


def parse_id(id_cls: Type[I], value: str | None) -> I | None:
    if value is None:
        return None
    with deserialization_guard(id_cls.__name__):
        return id_cls(value)


# --- time value objects ---------------------------------------------------


def serialize_duration(value: Duration | None) -> int | None:
    return value.minutes if value is not None else None


def parse_duration(value: int | None) -> Duration | None:
    if value is None:
        return None
    with deserialization_guard("Duration"):
        return Duration(value)


def serialize_time_range(value: TimeRange | None) -> dict | None:
    if value is None:
        return None
    return {
        "start": serialize_datetime(value.start),
        "end": serialize_datetime(value.end),
    }


def parse_time_range(value: dict | None) -> TimeRange | None:
    if value is None:
        return None
    with deserialization_guard("TimeRange"):
        return TimeRange(
            start=parse_datetime(value["start"]),
            end=parse_datetime(value["end"]),
        )


# --- resource flow --------------------------------------------------------


def serialize_resource_flow(flow: ResourceFlow) -> dict:
    return {
        "consumed": {rt.value: amount for rt, amount in flow.consumed.items()},
        "produced": {rt.value: amount for rt, amount in flow.produced.items()},
    }


def parse_resource_flow(value: dict | None) -> ResourceFlow:
    if value is None:
        return ResourceFlow.empty()
    with deserialization_guard("ResourceFlow"):
        return ResourceFlow(
            consumed={
                parse_enum(ResourceType, rt): amount
                for rt, amount in value.get("consumed", {}).items()
            },
            produced={
                parse_enum(ResourceType, rt): amount
                for rt, amount in value.get("produced", {}).items()
            },
        )


# --- event outcome --------------------------------------------------------


def serialize_outcome(outcome: EventOutcome | None) -> dict | None:
    if outcome is None:
        return None
    return {
        "outcome_type": serialize_enum(outcome.outcome_type),
        "recorded_at": serialize_datetime(outcome.recorded_at),
        "note": outcome.note,
    }


def parse_outcome(value: dict | None) -> EventOutcome | None:
    if value is None:
        return None
    with deserialization_guard("EventOutcome"):
        return EventOutcome(
            outcome_type=parse_enum(EventOutcomeType, value["outcome_type"]),
            recorded_at=parse_datetime(value["recorded_at"]),
            note=value.get("note"),
        )


# --- transition records ---------------------------------------------------


def serialize_transitions(records: tuple[TransitionRecord, ...]) -> list[dict]:
    """Serialize a transition history in order; order IS the history."""
    return [
        {
            "from_state": serialize_enum(record.from_state),
            "to_state": serialize_enum(record.to_state),
            "occurred_at": serialize_datetime(record.occurred_at),
            "actor": record.actor,
            "reason": record.reason,
        }
        for record in records
    ]


def parse_transition_records(
    enum_cls: Type[E], values: list[dict]
) -> tuple[TransitionRecord, ...]:
    """Parse persisted transition evidence into TransitionRecords, in order.

    Order IS the history. Structural validation of the chain (legal edges,
    continuity) is the domain's job — TransitionHistory.from_records — not
    the codec's.
    """
    records: list[TransitionRecord] = []
    with deserialization_guard(f"{enum_cls.__name__} transition history"):
        for value in values:
            records.append(
                TransitionRecord(
                    from_state=parse_enum(enum_cls, value["from_state"]),
                    to_state=parse_enum(enum_cls, value["to_state"]),
                    occurred_at=parse_datetime(value["occurred_at"]),
                    actor=value["actor"],
                    reason=value.get("reason"),
                )
            )
    return tuple(records)
