"""The formatter owns ALL presentation: clean human-readable text.

No JSON, no ANSI colour, no domain formatting anywhere else. Formatting
is duck-typed over facade outputs — the formatter reads attributes and
never imports lower layers.
"""

from datetime import datetime


def _time(moment: datetime | None) -> str:
    return moment.strftime("%Y-%m-%d %H:%M") if moment is not None else "-"


def _value(enum_like) -> str:
    return getattr(enum_like, "value", str(enum_like))


def format_status(status) -> str:
    context = status.execution_context
    context_line = "-"
    if context is not None:
        kind = type(context).__name__
        detail = ""
        if hasattr(context, "reason"):
            detail = f" ({_value(context.reason)})"
        elif hasattr(context, "event_id"):
            detail = f" (event {context.event_id})"
        context_line = f"{kind}{detail} since {_time(context.since)}"
    counts = ", ".join(
        f"{name}={count}"
        for name, count in sorted(status.aggregate_counts.items())
        if count
    )
    return "\n".join(
        (
            f"State:             {_value(status.state)}",
            f"Operational:       {'yes' if status.is_operational else 'no'}",
            f"Booted at:         {_time(status.booted_at)}",
            f"Execution context: {context_line}",
            f"Services:          {', '.join(status.registered_services) or '-'}",
            f"Latest snapshot:   {_time(status.latest_snapshot_at)}",
            f"Aggregates:        {counts or 'none'}",
        )
    )


def format_snapshot(snapshot) -> str:
    if snapshot is None:
        return "No snapshot available."
    running = (
        snapshot.running_event.description
        if snapshot.running_event is not None
        else "-"
    )
    return "\n".join(
        (
            f"Snapshot created:  {_time(snapshot.created_at)}",
            f"Current time:      {_time(snapshot.current_time)}",
            f"Running event:     {running}",
            f"Events:            {len(snapshot.events)}",
            f"Recommendations:   {len(snapshot.recommendations)}",
            f"Projects:          {len(snapshot.projects)}",
            f"Resources:         {len(snapshot.resources)}",
            f"Contexts:          {len(snapshot.contexts)}",
        )
    )


def format_recommendations(recommendations) -> str:
    if not recommendations:
        return "No active recommendations."
    lines = ["Active recommendations:"]
    for index, recommendation in enumerate(recommendations, start=1):
        priority = (
            f"{recommendation.priority:g}"
            if recommendation.priority is not None
            else "-"
        )
        confidence = (
            f"{recommendation.confidence_score:.2f}"
            if recommendation.confidence_score is not None
            else "-"
        )
        lines.append(
            f"{index}. [{_value(recommendation.status)}] "
            f"{recommendation.reason}"
        )
        lines.append(
            f"   priority {priority} | confidence {confidence} | "
            f"expires {_time(recommendation.expires_at)}"
        )
    return "\n".join(lines)


def format_events(events) -> str:
    if not events:
        return "No events."
    lines = ["Events:"]
    for index, event in enumerate(events, start=1):
        lines.append(
            f"{index}. [{_value(event.status)}] {event.description} "
            f"({event.category})"
        )
    return "\n".join(lines)


def format_event_detail(event) -> str:
    outcome = (
        _value(event.outcome.outcome_type) if event.outcome is not None else "-"
    )
    return "\n".join(
        (
            f"Event:        {event.event_id}",
            f"Description:  {event.description}",
            f"Category:     {event.category}",
            f"Status:       {_value(event.status)}",
            f"Started:      {_time(event.start_time)}",
            f"Ended:        {_time(event.end_time)}",
            f"Impact:       {_value(event.impact_type) if event.impact_type else '-'}",
            f"Outcome:      {outcome}",
            f"Actual:       {event.actual_outcome or '-'}",
            f"Transitions:  "
            + (
                " -> ".join(
                    _value(record.to_state) for record in event.transitions
                )
                or "-"
            ),
        )
    )


def format_context(snapshot) -> str:
    if snapshot is None:
        return "No snapshot available."
    lines = []
    context = snapshot.execution_context
    kind = type(context).__name__
    lines.append(f"Execution context: {kind} since {_time(context.since)}")
    window = snapshot.running_context_window
    if window is not None:
        lines.append(
            f"Active window:     {window.window_id} "
            f"[{_value(window.current_state)}]"
        )
    else:
        lines.append("Active window:     -")
    if snapshot.contexts:
        lines.append("Known contexts:")
        for index, known in enumerate(snapshot.contexts, start=1):
            location = f" @ {known.location}" if known.location else ""
            lines.append(f"{index}. {known.name}{location}")
    else:
        lines.append("Known contexts:    none")
    return "\n".join(lines)


def format_projects(snapshot) -> str:
    if snapshot is None or not snapshot.projects:
        return "No projects."
    completion_by_progress = {
        str(progress.progress_id): progress.completion_percentage
        for progress in snapshot.progress
    }
    lines = ["Projects:"]
    for index, project in enumerate(snapshot.projects, start=1):
        completion = completion_by_progress.get(
            str(project.progress_id), None
        )
        suffix = (
            f" — {completion:g}% complete" if completion is not None else ""
        )
        lines.append(
            f"{index}. [{_value(project.status)}] {project.name}{suffix}"
        )
    return "\n".join(lines)


def format_reflections(reflections) -> str:
    if not reflections:
        return "No reflections recorded."
    lines = ["Reflections:"]
    for index, reflection in enumerate(reflections, start=1):
        lesson = reflection.lesson_learned or reflection.interpretation or "-"
        lines.append(
            f"{index}. Event {reflection.event_id}: {lesson}"
        )
    return "\n".join(lines)


def format_decision_result(result) -> str:
    if result.no_action:
        return f"No action recommended.\n{result.no_action_reason}"
    lines = [f"{len(result.recommendations)} recommendation(s):"]
    for index, reasoned in enumerate(result.recommendations, start=1):
        lines.append(
            f"{index}. {reasoned.recommendation.reason} "
            f"(priority {reasoned.score.total:g}, "
            f"confidence {reasoned.explanation.confidence_level})"
        )
        lines.append(f"   why: {reasoned.explanation.why}")
        if reasoned.explanation.principles_influenced:
            lines.append(
                "   principles: "
                + ", ".join(reasoned.explanation.principles_influenced)
            )
    if result.rejected:
        lines.append(f"({len(result.rejected)} candidate(s) filtered out)")
    return "\n".join(lines)


def format_disturber(disturber) -> str:
    return (
        f"Disturbance recorded: [{_value(disturber.severity)}] "
        f"{disturber.description} — state {_value(disturber.state)}"
    )


def format_debug_scheduler(scheduler) -> str:
    plan = scheduler.plan
    lines = [f"Scheduler state: {_value(scheduler.state)}"]
    if plan is None or plan.is_empty:
        lines.append("Plan: empty")
    else:
        lines.append(f"Plan ({len(plan.entries)} entries):")
        for entry in plan.entries:
            lines.append(
                f"  {_time(entry.planned_start)} +{entry.duration_minutes}m "
                f"priority {entry.priority:g} -> event {entry.event_id}"
            )
    return "\n".join(lines)


def format_debug_kernel(kernel) -> str:
    latest = kernel.latest_snapshot
    return "\n".join(
        (
            f"Kernel state:   {_value(kernel.state)}",
            f"Services:       {', '.join(kernel.services.names()) or '-'}",
            f"Snapshot at:    "
            + (_time(latest.created_at) if latest is not None else "-"),
        )
    )


def format_debug_bus(bus) -> str:
    subscribers = getattr(bus, "_subscribers", {})
    if not subscribers:
        return "Event bus: no subscribers."
    lines = ["Event bus subscribers:"]
    for event_type in sorted(subscribers, key=lambda t: _value(t)):
        count = len(subscribers[event_type])
        if count:
            lines.append(f"  {_value(event_type)}: {count}")
    return "\n".join(lines)


# --- Milestone 10: entity management ------------------------------------


def _listing(title: str, items, line, empty: str) -> str:
    if not items:
        return empty
    lines = [title]
    for index, item in enumerate(items, start=1):
        lines.append(f"{index}. {line(item)}")
    return "\n".join(lines)


def _detail(pairs) -> str:
    width = max(len(label) for label, _ in pairs) + 1
    return "\n".join(
        f"{(label + ':'):<{width}} {value if value not in (None, '') else '-'}"
        for label, value in pairs
    )


def format_users(users) -> str:
    return _listing(
        "Users:",
        users,
        lambda user: f"{user.name} (last active {_time(user.last_active)})",
        "No users.",
    )


def format_user_detail(user) -> str:
    return _detail(
        (
            ("User", user.user_id),
            ("Name", user.name),
            ("Created", _time(user.created_at)),
            ("Last active", _time(user.last_active)),
        )
    )


def format_goals(goals) -> str:
    return _listing(
        "Goals:",
        goals,
        lambda goal: (
            f"[{_value(goal.status)}] {goal.name}"
            + ("" if goal.accepted_by_user else " (not yet accepted)")
        ),
        "No goals.",
    )


def format_goal_detail(goal) -> str:
    return _detail(
        (
            ("Goal", goal.goal_id),
            ("Name", goal.name),
            ("Description", goal.description),
            ("Status", _value(goal.status)),
            ("Suggested by", goal.suggested_by),
            ("Accepted", "yes" if goal.accepted_by_user else "no"),
            ("Accepted at", _time(goal.accepted_at)),
            ("Projects", ", ".join(str(p) for p in goal.related_project_ids)),
        )
    )


def format_project_list(projects) -> str:
    return _listing(
        "Projects:",
        projects,
        lambda project: f"[{_value(project.status)}] {project.name}",
        "No projects.",
    )


def format_project_detail(project, progress) -> str:
    pairs = [
        ("Project", project.project_id),
        ("Name", project.name),
        ("Description", project.description),
        ("Status", _value(project.status)),
        ("Created", _time(project.created_at)),
    ]
    if progress is not None:
        pairs.extend(
            (
                ("Completion", f"{progress.completion_percentage:g}%"),
                ("Velocity", f"{progress.velocity:g}"),
                ("Progress updated", _time(progress.last_updated)),
            )
        )
    return _detail(tuple(pairs))


def format_principles(principles) -> str:
    return _listing(
        "Principles:",
        principles,
        lambda principle: (
            f"[{_value(principle.category)}] {principle.name}"
        ),
        "No principles.",
    )


def format_principle_detail(principle) -> str:
    return _detail(
        (
            ("Principle", principle.principle_id),
            ("Name", principle.name),
            ("Description", principle.description),
            ("Category", _value(principle.category)),
            ("Created", _time(principle.created_at)),
            ("Last reviewed", _time(principle.last_reviewed)),
        )
    )


def format_resources(resources) -> str:
    return _listing(
        "Resources:",
        resources,
        lambda resource: (
            f"{resource.type.value} = {resource.current_value:g} "
            f"{resource.unit}"
        ),
        "No resources.",
    )


def format_resource_detail(resource) -> str:
    return _detail(
        (
            ("Resource", resource.resource_id),
            ("Type", _value(resource.type)),
            ("Value", f"{resource.current_value:g} {resource.unit}"),
            (
                "Negative allowed",
                "yes" if resource.negative_allowed else "no",
            ),
            ("Last updated", _time(resource.last_updated)),
        )
    )


def format_contexts(contexts) -> str:
    return _listing(
        "Contexts:",
        contexts,
        lambda context: context.name
        + (f" @ {context.location}" if context.location else ""),
        "No contexts.",
    )


def format_context_detail(context) -> str:
    return _detail(
        (
            ("Context", context.context_id),
            ("Name", context.name),
            ("Location", context.location),
            ("People", ", ".join(context.people)),
            ("Emotion", context.emotion),
            ("Trigger", context.trigger),
            ("Reason", context.reason),
            ("Environment", context.environment),
            ("Notes", context.notes),
            ("Created", _time(context.created_at)),
        )
    )


def format_knowledge(items) -> str:
    return _listing(
        "Knowledge:",
        items,
        lambda knowledge: (
            f"{knowledge.domain}/{knowledge.topic} — {knowledge.concept} "
            f"(confidence {knowledge.confidence:g})"
        ),
        "No knowledge recorded.",
    )


def format_knowledge_detail(knowledge) -> str:
    return _detail(
        (
            ("Knowledge", knowledge.knowledge_id),
            ("Domain", knowledge.domain),
            ("Topic", knowledge.topic),
            ("Concept", knowledge.concept),
            ("Project", knowledge.project_id),
            ("Difficulty", knowledge.difficulty),
            ("Confidence", f"{knowledge.confidence:g}"),
            ("Revisions", knowledge.revision_count),
            ("Last revision", _time(knowledge.last_revision)),
            ("Source", knowledge.source),
            ("Applied", "yes" if knowledge.applied else "no"),
            ("Retention", f"{knowledge.retention_score:g}"),
        )
    )


def format_reflection_detail(reflection) -> str:
    return _detail(
        (
            ("Reflection", reflection.reflection_id),
            ("Event", reflection.event_id),
            ("Context window", reflection.context_window_id),
            ("Created", _time(reflection.created_at)),
            ("Facts", reflection.facts),
            ("Interpretation", reflection.interpretation),
            ("Root cause", reflection.root_cause),
            ("Lesson learned", reflection.lesson_learned),
            ("Improvement", reflection.improvement),
            (
                "Confidence",
                f"{reflection.confidence:g}"
                if reflection.confidence is not None
                else None,
            ),
        )
    )


def format_habits(habits) -> str:
    return _listing(
        "Habits (read-only; detected by the Learning Engine):",
        habits,
        lambda habit: f"{habit.name} (strength {habit.strength:g})",
        "No habits detected.",
    )


def format_habit_detail(habit) -> str:
    return _detail(
        (
            ("Habit", habit.habit_id),
            ("Name", habit.name),
            ("Detected", _time(habit.detected_at)),
            ("Trigger", habit.trigger),
            ("Frequency", habit.frequency),
            ("Reward", habit.reward),
            ("Trend", habit.current_trend),
            ("Strength", f"{habit.strength:g}"),
            ("Desired state", habit.desired_state),
            ("Last updated", _time(habit.last_updated)),
        )
    )


def format_insights(insights) -> str:
    return _listing(
        "Insights (read-only; extracted by the Learning Engine):",
        insights,
        lambda insight: (
            f"[{insight.category or 'uncategorized'}] "
            f"from reflection {insight.source_reflection_id}"
        ),
        "No insights extracted.",
    )


def format_insight_detail(insight) -> str:
    return _detail(
        (
            ("Insight", insight.insight_id),
            ("Source reflection", insight.source_reflection_id),
            ("Category", insight.category),
            (
                "Confidence",
                f"{insight.confidence:g}"
                if insight.confidence is not None
                else None,
            ),
            ("Reusable", "yes" if insight.reusable else "no"),
            ("Created", _time(insight.created_at)),
        )
    )


def format_help(specs, command: str | None = None) -> str:
    if command is not None:
        spec = specs.get(command)
        if spec is None:
            return f"Unknown command: {command!r}."
        return f"{spec.usage}\n  {spec.description}"
    lines = ["PAIOS commands:"]
    for spec in specs.values():
        lines.append(f"  {spec.usage:<45} {spec.description}")
    lines.append("  shell                                         Interactive mode")
    lines.append("  exit / quit                                   Leave the shell")
    return "\n".join(lines)
