"""History extraction: normalize immutable evidence into observations.

Pure, deterministic, mutation-free: every derived structure is built from
sorted iteration over the input; the input is never touched. Timestamps
come only from the data itself.
"""

from dataclasses import dataclass
from datetime import datetime

from paios.domain.entities.event import Event
from paios.domain.enums import EventStatus
from paios.learning.exceptions import InvalidHistoryError
from paios.learning.history import History


def reached(event: Event, status: EventStatus) -> bool:
    """Whether the Event's evidence trail passed through a state — Archived
    Events keep counting as what they were (History is immutable)."""
    return any(record.to_state is status for record in event.transitions)


def anchor_time(event: Event) -> datetime | None:
    """The moment an Event is attributed to, derived from its evidence."""
    if event.end_time is not None:
        return event.end_time
    if event.transitions:
        return event.transitions[-1].occurred_at
    return event.start_time


def category_of(event: Event) -> str:
    return event.category.strip().lower()


@dataclass(frozen=True)
class AnalysisWindow:
    start: datetime
    end: datetime

    @property
    def midpoint(self) -> datetime:
        return self.start + (self.end - self.start) / 2


@dataclass(frozen=True)
class Observations:
    """Normalized, sorted view of one History for the analyzers."""

    window: AnalysisWindow | None
    completed: tuple[Event, ...]
    skipped: tuple[Event, ...]
    cancelled: tuple[Event, ...]
    interrupted: tuple[Event, ...]
    categories: tuple[str, ...]  # sorted distinct categories of all events

    def completed_in(self, category: str) -> tuple[Event, ...]:
        return tuple(
            event
            for event in self.completed
            if category_of(event) == category.lower()
        )

    def split_halves(
        self, events: tuple[Event, ...]
    ) -> tuple[tuple[Event, ...], tuple[Event, ...]]:
        """Deterministic first-half/second-half split of the window."""
        if self.window is None:
            return (), ()
        midpoint = self.window.midpoint
        first, second = [], []
        for event in events:
            moment = anchor_time(event)
            if moment is None:
                continue
            (first if moment <= midpoint else second).append(event)
        return tuple(first), tuple(second)


def _sorted_events(events, status: EventStatus) -> tuple[Event, ...]:
    matched = [event for event in events if reached(event, status)]
    matched.sort(
        key=lambda event: (
            anchor_time(event) or datetime.min,
            str(event.event_id),
        )
    )
    return tuple(matched)


def resolve_as_of(history: History, as_of: datetime | None) -> datetime | None:
    """The analysis anchor: caller-supplied, else the newest timestamp in
    the data itself — never a clock."""
    if as_of is not None:
        return as_of
    moments: list[datetime] = []
    for event in history.events:
        moment = anchor_time(event)
        if moment is not None:
            moments.append(moment)
    moments.extend(r.created_at for r in history.reflections)
    moments.extend(d.occurred_at for d in history.event_disturbers)
    return max(moments) if moments else None


def extract(history: History, as_of: datetime | None = None) -> Observations:
    if not isinstance(history, History):
        raise InvalidHistoryError(
            "The Learning Engine analyzes History views only"
        )
    resolved = resolve_as_of(history, as_of)
    window: AnalysisWindow | None = None
    if resolved is not None:
        starts: list[datetime] = []
        for event in history.events:
            moment = event.start_time or anchor_time(event)
            if moment is not None:
                starts.append(moment)
        start = min(starts) if starts else resolved
        window = AnalysisWindow(start=min(start, resolved), end=resolved)
    categories = tuple(
        sorted({category_of(event) for event in history.events})
    )
    return Observations(
        window=window,
        completed=_sorted_events(history.events, EventStatus.COMPLETED),
        skipped=_sorted_events(history.events, EventStatus.SKIPPED),
        cancelled=_sorted_events(history.events, EventStatus.CANCELLED),
        interrupted=_sorted_events(history.events, EventStatus.INTERRUPTED),
        categories=categories,
    )
