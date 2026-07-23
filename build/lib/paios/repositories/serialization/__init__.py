"""Lossless JSON serialization for every domain aggregate and value object.

Serializers turn domain objects into plain JSON-safe dicts; deserializers
rebuild domain objects exclusively through the domain's PUBLIC API —
constructors and lifecycle methods — replaying persisted transitions in
order so that append-only history, immutability guards, and state-machine
validation all survive persistence. A persisted record the domain would
reject is reported as SerializationError, never silently loaded.
"""

from paios.repositories.serialization.serializers import (
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
from paios.repositories.serialization.deserializers import (
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
)

__all__ = [name for name in dir() if name.startswith(("serialize_", "deserialize_"))]
