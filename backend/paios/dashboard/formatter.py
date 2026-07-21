"""Value formatting for the dashboard: pure functions, duck-typed inputs.

Like the CLI formatter, everything here reads attributes and never imports
domain modules — facade outputs are formatted, not interpreted. State
names are compared as their canonical string values (GLOSSARY.md); that is
string matching for display grouping, not business logic.
"""

from datetime import datetime

#: Canonical Event state names (STATE_MACHINES.md section 1), as strings.
RUNNING_STATE_NAMES = ("Started", "Resumed")
COMPLETED_STATE_NAME = "Completed"
UPCOMING_STATE_NAMES = ("Recommended", "Scheduled", "Ready")


def value(enum_like) -> str:
    return getattr(enum_like, "value", str(enum_like))


def clock_time(moment: datetime | None) -> str:
    return moment.strftime("%Y-%m-%d %H:%M:%S") if moment is not None else "-"


def short_time(moment: datetime | None) -> str:
    return moment.strftime("%H:%M") if moment is not None else "-"


def day(moment: datetime | None) -> str:
    return moment.strftime("%Y-%m-%d") if moment is not None else "-"


def minutes_label(total_minutes: int) -> str:
    if total_minutes < 0:
        total_minutes = 0
    hours, minutes = divmod(int(total_minutes), 60)
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"


def elapsed_minutes(start: datetime | None, now: datetime) -> int | None:
    if start is None:
        return None
    return max(0, int((now - start).total_seconds() // 60))


def remaining_minutes(
    start: datetime | None, duration_minutes: int | None, now: datetime
) -> int | None:
    if start is None or duration_minutes is None:
        return None
    elapsed = elapsed_minutes(start, now) or 0
    return max(0, duration_minutes - elapsed)


def progress_bar(percentage: float, width: int = 20) -> str:
    bounded = min(100.0, max(0.0, percentage))
    filled = int(round(bounded / 100.0 * width))
    return "[" + "#" * filled + "." * (width - filled) + f"] {bounded:g}%"


def started_moment(event) -> datetime | None:
    """When execution began: the explicit start_time when set, else the
    moment of the most recent Started/Resumed transition (the Scheduler
    records timing as lifecycle evidence, not on the Event fields)."""
    if getattr(event, "start_time", None) is not None:
        return event.start_time
    for record in reversed(getattr(event, "transitions", ()) or ()):
        if value(record.to_state) in RUNNING_STATE_NAMES:
            return record.occurred_at
    return None


def is_running(event) -> bool:
    return value(event.status) in RUNNING_STATE_NAMES


def is_completed(event) -> bool:
    return value(event.status) == COMPLETED_STATE_NAME


def is_upcoming(event) -> bool:
    return value(event.status) in UPCOMING_STATE_NAMES


def same_day(moment: datetime | None, reference: datetime) -> bool:
    return moment is not None and moment.date() == reference.date()


def event_line(event) -> str:
    return f"[{value(event.status)}] {event.description}"


def recommendation_line(recommendation) -> str:
    priority = (
        f"{recommendation.priority:g}"
        if getattr(recommendation, "priority", None) is not None
        else "-"
    )
    return f"({priority}) {recommendation.reason}"


def goal_line(goal) -> str:
    marker = "*" if getattr(goal, "accepted_by_user", False) else "?"
    return f"{marker} [{value(goal.status)}] {goal.name}"


def disturber_line(disturber) -> str:
    return (
        f"[{value(disturber.severity)}] {disturber.description} "
        f"({value(disturber.state)})"
    )
