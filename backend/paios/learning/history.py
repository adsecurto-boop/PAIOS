"""The History input view and its repository-interface loader.

The engine core is a pure function over this immutable view. The loader
is the ONLY place that touches persistence, and it touches interfaces
exclusively (list() reads — reconstitution and structural validation are
the repositories' own concern). It never sees Runtime State, Scheduler
state, or persistence internals.
"""

from dataclasses import dataclass
from typing import Protocol

from paios.domain.entities.event import Event
from paios.domain.entities.event_disturber import EventDisturber
from paios.domain.entities.habit import Habit
from paios.domain.entities.principle import Principle
from paios.domain.entities.reflection import Reflection
from paios.repositories.interfaces import (
    EventDisturberRepository,
    EventRepository,
    HabitRepository,
    PrincipleRepository,
    ReflectionRepository,
)


@dataclass(frozen=True)
class History:
    """Immutable evidence: everything the Learning Engine may observe."""

    events: tuple[Event, ...] = ()
    reflections: tuple[Reflection, ...] = ()
    event_disturbers: tuple[EventDisturber, ...] = ()
    habits: tuple[Habit, ...] = ()
    principles: tuple[Principle, ...] = ()


class HistoryProvider(Protocol):
    """Structural contract satisfied by RepositoryFactory — interfaces only."""

    def events(self) -> EventRepository: ...
    def reflections(self) -> ReflectionRepository: ...
    def event_disturbers(self) -> EventDisturberRepository: ...
    def habits(self) -> HabitRepository: ...
    def principles(self) -> PrincipleRepository: ...


class HistoryLoader:
    """Reads persisted history through repository interfaces."""

    def __init__(self, provider: HistoryProvider) -> None:
        self._provider = provider

    def load(self) -> History:
        return History(
            events=tuple(self._provider.events().list()),
            reflections=tuple(self._provider.reflections().list()),
            event_disturbers=tuple(self._provider.event_disturbers().list()),
            habits=tuple(self._provider.habits().list()),
            principles=tuple(self._provider.principles().list()),
        )
