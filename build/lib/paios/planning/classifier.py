"""Deterministic capture classification: the offline planning brain.

Classifies free-text capture lines into goal / project / event / inbox
and detects duplicates against existing work. Pure functions over
supplied inputs — no clock, no I/O, no randomness — so the Planning
Workspace works fully offline; when an LLM adapter is configured the
AI Assistant refines these results (and only proposes, never creates).
"""

from dataclasses import dataclass, field

#: Verbs/nouns that read as a long-running aspiration.
_GOAL_MARKERS = (
    "become", "learn", "master", "improve", "achieve", "grow",
    "lose weight", "get fit", "save money", "certification",
)
#: Markers of multi-step buildable work.
_PROJECT_MARKERS = (
    "build", "create", "develop", "research", "write", "design",
    "implement", "launch", "organize", "plan the", "migrate",
)
#: Markers of a single concrete action.
_EVENT_MARKERS = (
    "buy", "call", "visit", "go to", "attend", "book", "pay", "send",
    "read chapter", "practice", "study", "gym", "temple", "office",
    "meeting", "appointment", "haircut", "clean", "medicine", "pick up",
)
#: Day headers that scope the lines below them, not items themselves.
_DAY_HEADERS = (
    "today", "tomorrow", "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday", "next week", "this week",
)


@dataclass(frozen=True)
class ClassifiedLine:
    text: str
    kind: str  # goal | project | event | inbox | day_header
    day_scope: str | None = None
    duplicate_of: str | None = None  # name of the matching existing work
    similar_to: tuple[str, ...] = field(default_factory=tuple)


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _tokens(text: str) -> set[str]:
    return {token for token in _normalize(text).split() if len(token) > 2}


def _overlap(a: str, b: str) -> float:
    tokens_a, tokens_b = _tokens(a), _tokens(b)
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / min(len(tokens_a), len(tokens_b))


def _kind_of(line: str) -> str:
    lowered = _normalize(line)
    for marker in _EVENT_MARKERS:
        if marker in lowered:
            return "event"
    for marker in _PROJECT_MARKERS:
        if lowered.startswith(marker) or f" {marker}" in f" {lowered}":
            return "project"
    for marker in _GOAL_MARKERS:
        if marker in lowered:
            return "goal"
    # Short concrete phrases default to events; everything else lands in
    # the inbox for the user to triage.
    return "event" if len(lowered.split()) <= 4 else "inbox"


def classify_lines(
    text: str,
    existing_goals: tuple[str, ...] = (),
    existing_projects: tuple[str, ...] = (),
    existing_events: tuple[str, ...] = (),
) -> tuple[ClassifiedLine, ...]:
    """Classify a captured block line by line, deterministically.

    Duplicate = normalized-equal to existing work of the matching kind;
    similar = token overlap >= 0.6 against any existing work.
    """
    existing_by_kind = {
        "goal": existing_goals,
        "project": existing_projects,
        "event": existing_events,
    }
    all_existing = existing_goals + existing_projects + existing_events
    results: list[ClassifiedLine] = []
    day_scope: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip().lstrip("-*").strip()
        if not line:
            continue
        lowered = _normalize(line)
        if lowered in _DAY_HEADERS:
            day_scope = lowered
            results.append(
                ClassifiedLine(text=line, kind="day_header", day_scope=lowered)
            )
            continue

        kind = _kind_of(line)
        duplicate = next(
            (
                name
                for name in existing_by_kind.get(kind, ())
                if _normalize(name) == lowered
            ),
            None,
        )
        similar = tuple(
            name
            for name in all_existing
            if _normalize(name) != lowered and _overlap(line, name) >= 0.6
        )
        results.append(
            ClassifiedLine(
                text=line,
                kind=kind,
                day_scope=day_scope,
                duplicate_of=duplicate,
                similar_to=similar,
            )
        )
    return tuple(results)
