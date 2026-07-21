"""Deterministic context: immutable snapshots -> canonical prompt text.

Identical snapshot -> identical text, byte for byte. The rules that
guarantee it:

- inputs are READ via duck-typed attribute access (never mutated,
  never called beyond attribute reads);
- every collection is sorted by a stable key before rendering;
- no clocks, no randomness, no environment: only the received values;
- enums render as their `.value`, datetimes as ISO-8601, identifiers
  as `str()`.
"""


def _value(enum_like) -> str:
    return str(getattr(enum_like, "value", enum_like))


def _iso(moment) -> str:
    return moment.isoformat() if moment is not None else "-"


def _get(entity, name, default="-"):
    result = getattr(entity, name, default)
    return default if result is None else result


# --- per-collection blocks (each line is one item, sorted) -----------------


def recommendation_line(recommendation) -> str:
    return (
        f"- [{_value(_get(recommendation, 'status'))}] "
        f"{_get(recommendation, 'reason')} "
        f"(priority={_get(recommendation, 'priority')}, "
        f"confidence={_get(recommendation, 'confidence_score')}, "
        f"expires={_iso(getattr(recommendation, 'expires_at', None))})"
    )


def event_line(event) -> str:
    return (
        f"- [{_value(_get(event, 'status'))}] {_get(event, 'description')} "
        f"(category={_get(event, 'category')}, "
        f"start={_iso(getattr(event, 'start_time', None))}, "
        f"duration={getattr(getattr(event, 'duration', None), 'minutes', '-')}m, "
        f"outcome={_value(_get(event, 'actual_outcome'))})"
    )


def goal_line(goal) -> str:
    return (
        f"- [{_value(_get(goal, 'status'))}] {_get(goal, 'name')}: "
        f"{_get(goal, 'description')}"
    )


def project_line(project) -> str:
    return (
        f"- [{_value(_get(project, 'status'))}] {_get(project, 'name')}: "
        f"{_get(project, 'description')}"
    )


def resource_line(resource) -> str:
    return (
        f"- {_value(_get(resource, 'type'))}: "
        f"{_get(resource, 'current_value')} {_get(resource, 'unit')}"
    )


def habit_line(habit) -> str:
    return (
        f"- {_get(habit, 'name')} (strength={_get(habit, 'strength')}, "
        f"trend={_get(habit, 'current_trend')})"
    )


def insight_line(insight) -> str:
    return (
        f"- [{_get(insight, 'category')}] "
        f"confidence={_get(insight, 'confidence')} "
        f"reusable={_get(insight, 'reusable')}"
    )


def principle_line(principle) -> str:
    return (
        f"- {_get(principle, 'name')} "
        f"[{_value(_get(principle, 'category'))}]: "
        f"{_get(principle, 'description')}"
    )


def knowledge_line(knowledge) -> str:
    return (
        f"- {_get(knowledge, 'domain')}/{_get(knowledge, 'topic')}: "
        f"{_get(knowledge, 'concept')} "
        f"(confidence={_get(knowledge, 'confidence')}, "
        f"revisions={_get(knowledge, 'revision_count')}, "
        f"last={_iso(getattr(knowledge, 'last_revision', None))})"
    )


def reflection_line(reflection) -> str:
    return (
        f"- {_iso(getattr(reflection, 'created_at', None))}: "
        f"lesson={_get(reflection, 'lesson_learned')} "
        f"improvement={_get(reflection, 'improvement')}"
    )


def context_line(context) -> str:
    return (
        f"- {_get(context, 'name')} (location={_get(context, 'location')}, "
        f"reason={_get(context, 'reason')})"
    )


#: Section title -> line renderer, in fixed render order.
_SECTIONS = (
    ("Recommendations", "recommendations", recommendation_line),
    ("Events", "events", event_line),
    ("Goals", "goals", goal_line),
    ("Projects", "projects", project_line),
    ("Resources", "resources", resource_line),
    ("Habits", "habits", habit_line),
    ("Insights", "insights", insight_line),
    ("Principles", "principles", principle_line),
    ("Knowledge", "knowledge", knowledge_line),
    ("Reflections", "reflections", reflection_line),
    ("Contexts", "contexts", context_line),
)


def snapshot_block(snapshot) -> str:
    """A RuntimeSnapshot header: the runtime situation in four lines."""
    if snapshot is None:
        return "Runtime: no snapshot provided."
    running = getattr(snapshot, "running_event", None)
    return "\n".join(
        (
            f"Snapshot time: {_iso(getattr(snapshot, 'current_time', None))}",
            "Execution context: "
            f"{type(getattr(snapshot, 'execution_context', None)).__name__}",
            "Running event: "
            + (
                f"{_get(running, 'description')}"
                if running is not None
                else "none (idle)"
            ),
            f"Events held: {len(tuple(getattr(snapshot, 'events', ()) or ()))}",
        )
    )


def learning_block(learning_result) -> str:
    """A LearningResult summary: findings/trends/insights, sorted."""
    if learning_result is None:
        return "Learning: no learning result provided."
    lines = ["Learning result:"]
    for label, attribute in (
        ("findings", "findings"),
        ("trends", "trends"),
        ("insights", "insights"),
        ("candidate principles", "candidate_principles"),
        ("candidate habit changes", "candidate_habit_changes"),
    ):
        items = tuple(getattr(learning_result, attribute, ()) or ())
        lines.append(f"- {label}: {len(items)}")
    for trend in _sorted(getattr(learning_result, "trends", ()) or ()):
        lines.append(f"  trend: {_describe(trend)}")
    for insight in _sorted(getattr(learning_result, "insights", ()) or ()):
        lines.append(f"  insight: {_describe(insight)}")
    return "\n".join(lines)


def _describe(item) -> str:
    for attribute in ("description", "summary", "category", "name"):
        value = getattr(item, attribute, None)
        if isinstance(value, str) and value:
            return value
    return type(item).__name__


def _sorted(items):
    return sorted(items, key=lambda item: repr(_stable_key(item)))


def _stable_key(item):
    for attribute in (
        "name", "description", "reason", "created_at", "domain",
    ):
        value = getattr(item, attribute, None)
        if value is not None:
            return str(value)
    return str(item)


def build_context(
    snapshot=None,
    learning_result=None,
    **collections,
) -> str:
    """Render every provided input into one canonical context text.

    ``collections`` accepts the mission's inputs by name (events=,
    goals=, projects=, resources=, habits=, insights=, principles=,
    knowledge=, reflections=, recommendations=, contexts=). Unknown
    names are an error — silent typos would silently drop context.
    """
    known = {name for _, name, _ in _SECTIONS}
    unknown = sorted(set(collections) - known)
    if unknown:
        raise KeyError(f"Unknown context collections: {unknown}")

    parts = [snapshot_block(snapshot)]
    if learning_result is not None:
        parts.append(learning_block(learning_result))
    for title, name, renderer in _SECTIONS:
        items = collections.get(name)
        if items is None:
            continue
        ordered = _sorted(tuple(items))
        body = "\n".join(renderer(item) for item in ordered) or "(none)"
        parts.append(f"{title}:\n{body}")
    return "\n\n".join(parts)
