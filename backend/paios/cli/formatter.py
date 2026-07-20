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
