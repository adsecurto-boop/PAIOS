"""DDD entity base: identity-based equality.

Two entity instances are the same entity when they are the same type and
carry the same identifier, regardless of attribute state.
"""

from typing import Any, ClassVar


class Entity:
    """Mixin giving entities equality and hashing by their identifier."""

    _id_attr: ClassVar[str] = ""

    def __eq__(self, other: Any) -> bool:
        if type(other) is not type(self):
            return NotImplemented
        return getattr(other, self._id_attr) == getattr(self, self._id_attr)

    def __hash__(self) -> int:
        return hash((type(self), getattr(self, self._id_attr)))
