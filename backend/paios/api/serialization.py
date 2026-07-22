"""Entity/value -> JSON-safe dict serialization.

Duck-typed over facade outputs, exactly like the CLI and TUI formatters:
identifiers become strings, enums their values, datetimes ISO-8601.
The dashboard payload mirrors the TUI dashboard section for section so
GET /dashboard returns exactly the information the TUI shows.
"""

from datetime import datetime

#: Canonical Event state names (STATE_MACHINES.md), as display strings —
#: the same grouping the TUI dashboard uses.
_RUNNING = ("Started", "Resumed")
_UPCOMING = ("Recommended", "Scheduled", "Ready")
_HEALTH_RESOURCE_TYPES = ("Health", "Energy", "Stress")


def _value(enum_like):
    return getattr(enum_like, "value", str(enum_like))


def _identifier(identifier) -> str | None:
    return str(identifier) if identifier is not None else None


def _iso(moment: datetime | None) -> str | None:
    return moment.isoformat() if moment is not None else None


# --- system ---------------------------------------------------------------


def serialize_status(status) -> dict:
    context = status.execution_context
    return {
        "state": _value(status.state),
        "operational": status.is_operational,
        "booted_at": _iso(status.booted_at),
        "execution_context": (
            type(context).__name__ if context is not None else None
        ),
        "services": list(status.registered_services),
        "aggregate_counts": dict(status.aggregate_counts),
        "latest_snapshot_at": _iso(status.latest_snapshot_at),
    }


def serialize_snapshot(snapshot) -> dict | None:
    if snapshot is None:
        return None
    return {
        "created_at": _iso(snapshot.created_at),
        "current_time": _iso(snapshot.current_time),
        "execution_context": type(snapshot.execution_context).__name__,
        "running_event": (
            _identifier(snapshot.running_event.event_id)
            if snapshot.running_event is not None
            else None
        ),
        "counts": {
            "events": len(snapshot.events),
            "recommendations": len(snapshot.recommendations),
            "projects": len(snapshot.projects),
            "resources": len(snapshot.resources),
            "contexts": len(snapshot.contexts),
            "goals": len(snapshot.goals),
            "reflections": len(snapshot.reflections),
        },
    }


def serialize_decision_result(result) -> dict:
    return {
        "no_action": result.no_action,
        "no_action_reason": getattr(result, "no_action_reason", None),
        "recommendations": [
            {
                "recommendation_id": _identifier(
                    reasoned.recommendation.recommendation_id
                ),
                "reason": reasoned.recommendation.reason,
                "priority": reasoned.score.total,
                "confidence": reasoned.explanation.confidence_level,
                "why": reasoned.explanation.why,
            }
            for reasoned in result.recommendations
        ],
        "rejected_count": len(result.rejected),
    }


# --- plan (M20) -------------------------------------------------------------


def serialize_plan(plan) -> dict:
    """SchedulingPlan -> JSON. Read-only Scheduler output; the timeline's
    data source."""
    if plan is None:
        return {"created_at": None, "entries": []}
    return {
        "created_at": _iso(plan.created_at),
        "entries": [
            {
                "event_id": _identifier(entry.event_id),
                "planned_start": _iso(entry.planned_start),
                "planned_end": _iso(entry.planned_end),
                "duration_minutes": entry.duration_minutes,
                "priority": entry.priority,
                "recommendation_id": _identifier(entry.recommendation_id),
            }
            for entry in plan.entries
        ],
    }


def serialize_proposed(recommendation, event_id) -> dict:
    """The POST /events reply: the admitted intent plus the materialized
    event id when the Scheduler's cycle already produced one."""
    return {
        "recommendation": serialize_recommendation(recommendation),
        "event_id": _identifier(event_id),
        "materialized": event_id is not None,
    }


# --- aggregates -----------------------------------------------------------


def serialize_recommendation(recommendation) -> dict:
    return {
        "recommendation_id": _identifier(recommendation.recommendation_id),
        "status": _value(recommendation.status),
        "reason": recommendation.reason,
        "priority": recommendation.priority,
        "confidence_score": recommendation.confidence_score,
        "expires_at": _iso(recommendation.expires_at),
    }


def serialize_event(event) -> dict:
    return {
        "event_id": _identifier(event.event_id),
        "user_id": _identifier(event.user_id),
        "description": event.description,
        "category": event.category,
        "status": _value(event.status),
        "project_id": _identifier(event.project_id),
        "context_window_id": _identifier(event.context_window_id),
        "start_time": _iso(event.start_time),
        "end_time": _iso(event.end_time),
        "duration_minutes": getattr(event.duration, "minutes", None),
        "impact_type": (
            _value(event.impact_type) if event.impact_type else None
        ),
        "outcome": (
            _value(event.outcome.outcome_type)
            if event.outcome is not None
            else None
        ),
        "actual_outcome": event.actual_outcome,
        "reflection_id": _identifier(event.reflection_id),
        "transitions": [
            {
                "to_state": _value(record.to_state),
                "occurred_at": _iso(record.occurred_at),
                "actor": record.actor,
            }
            for record in event.transitions
        ],
    }


def serialize_goal(goal) -> dict:
    return {
        "goal_id": _identifier(goal.goal_id),
        "user_id": _identifier(goal.user_id),
        "name": goal.name,
        "description": goal.description,
        "status": _value(goal.status),
        "suggested_by": goal.suggested_by,
        "accepted_by_user": goal.accepted_by_user,
        "accepted_at": _iso(goal.accepted_at),
        "related_project_ids": [
            str(p) for p in goal.related_project_ids
        ],
    }


def serialize_project(project, progress=None) -> dict:
    serialized = {
        "project_id": _identifier(project.project_id),
        "user_id": _identifier(project.user_id),
        "name": project.name,
        "description": project.description,
        "status": _value(project.status),
        "created_at": _iso(project.created_at),
        "progress_id": _identifier(project.progress_id),
    }
    if progress is not None:
        serialized["progress"] = {
            "completion_percentage": progress.completion_percentage,
            "velocity": progress.velocity,
            "confidence": progress.confidence,
            "last_updated": _iso(progress.last_updated),
        }
    else:
        serialized["progress"] = None
    return serialized


def serialize_resource(resource) -> dict:
    return {
        "resource_id": _identifier(resource.resource_id),
        "user_id": _identifier(resource.user_id),
        "type": _value(resource.type),
        "current_value": resource.current_value,
        "unit": resource.unit,
        "negative_allowed": resource.negative_allowed,
        "last_updated": _iso(resource.last_updated),
    }


def serialize_knowledge(knowledge) -> dict:
    return {
        "knowledge_id": _identifier(knowledge.knowledge_id),
        "user_id": _identifier(knowledge.user_id),
        "domain": knowledge.domain,
        "topic": knowledge.topic,
        "concept": knowledge.concept,
        "project_id": _identifier(knowledge.project_id),
        "difficulty": knowledge.difficulty,
        "confidence": knowledge.confidence,
        "revision_count": knowledge.revision_count,
        "last_revision": _iso(knowledge.last_revision),
        "source": knowledge.source,
        "applied": knowledge.applied,
        "retention_score": knowledge.retention_score,
    }


def serialize_reflection(reflection) -> dict:
    return {
        "reflection_id": _identifier(reflection.reflection_id),
        "event_id": _identifier(reflection.event_id),
        "context_window_id": _identifier(reflection.context_window_id),
        "created_at": _iso(reflection.created_at),
        "facts": reflection.facts,
        "interpretation": reflection.interpretation,
        "root_cause": reflection.root_cause,
        "lesson_learned": reflection.lesson_learned,
        "improvement": reflection.improvement,
        "confidence": reflection.confidence,
    }


def serialize_context(context) -> dict:
    return {
        "context_id": _identifier(context.context_id),
        "name": context.name,
        "created_at": _iso(context.created_at),
        "location": context.location,
        "people": list(context.people),
        "emotion": context.emotion,
        "trigger": context.trigger,
        "reason": context.reason,
        "environment": context.environment,
        "notes": context.notes,
    }


def serialize_disturber(disturber) -> dict:
    return {
        "event_disturber_id": _identifier(disturber.event_disturber_id),
        "type": _value(disturber.type),
        "severity": _value(disturber.severity),
        "description": disturber.description,
        "state": _value(disturber.state),
    }


def serialize_habit(habit) -> dict:
    return {
        "habit_id": _identifier(habit.habit_id),
        "name": habit.name,
        "strength": habit.strength,
        "current_trend": habit.current_trend,
        "detected_at": _iso(habit.detected_at),
    }


def serialize_insight(insight) -> dict:
    return {
        "insight_id": _identifier(insight.insight_id),
        "source_reflection_id": _identifier(insight.source_reflection_id),
        "category": insight.category,
        "confidence": insight.confidence,
        "reusable": insight.reusable,
        "created_at": _iso(insight.created_at),
    }


# --- dashboard (TUI parity) -----------------------------------------------


def _started_moment(event):
    """Same rule as the TUI: explicit start_time, else the most recent
    Started/Resumed transition (the Scheduler records timing as
    lifecycle evidence)."""
    if event.start_time is not None:
        return event.start_time
    for record in reversed(event.transitions or ()):
        if _value(record.to_state) in _RUNNING:
            return record.occurred_at
    return None


def dashboard_payload(application) -> dict:
    """The TUI dashboard's information, section for section, as JSON."""
    now = application.current_time()
    events = application.list_events()
    running = [e for e in events if _value(e.status) in _RUNNING]
    completed_today = [
        e
        for e in events
        if _value(e.status) == "Completed"
        and (e.end_time or e.start_time) is not None
        and (e.end_time or e.start_time).date() == now.date()
    ]
    upcoming = [e for e in events if _value(e.status) in _UPCOMING]

    current_event = None
    if running:
        event = running[0]
        started = _started_moment(event)
        duration = getattr(event.duration, "minutes", None)
        elapsed = (
            max(0, int((now - started).total_seconds() // 60))
            if started is not None
            else None
        )
        current_event = {
            "event_id": _identifier(event.event_id),
            "description": event.description,
            "status": _value(event.status),
            "started_at": _iso(started),
            "elapsed_minutes": elapsed,
            "duration_minutes": duration,
            "remaining_minutes": (
                max(0, duration - elapsed)
                if duration is not None and elapsed is not None
                else None
            ),
        }

    snapshot = application.snapshot()
    if snapshot is not None:
        context = snapshot.execution_context
        window = snapshot.running_context_window
        current_context = {
            "execution_context": type(context).__name__,
            "reason": (
                _value(context.reason) if hasattr(context, "reason") else None
            ),
            "since": _iso(context.since),
            "context_window": (
                {
                    "window_id": _identifier(window.window_id),
                    "state": _value(window.current_state),
                }
                if window is not None
                else None
            ),
        }
    else:
        current_context = None

    knowledge = application.list_knowledge()
    reflections = application.list_reflections()
    insights = application.list_insights()
    status = application.status()

    return {
        "current_time": _iso(now),
        "current_event": current_event,
        "current_context": current_context,
        "active_disturbers": [
            serialize_disturber(d)
            for d in application.active_event_disturbers()
        ],
        "recommendations": [
            serialize_recommendation(r)
            for r in application.active_recommendations()
        ],
        "goals": [serialize_goal(g) for g in application.list_goals()],
        "projects": [
            serialize_project(
                project,
                application.get_project_progress(project.project_id),
            )
            for project in application.list_projects()
        ],
        "today": {
            "completed": [serialize_event(e) for e in completed_today],
            "running": [serialize_event(e) for e in running],
            "upcoming": [serialize_event(e) for e in upcoming],
        },
        "health": {
            "resources": [
                serialize_resource(r)
                for r in application.list_resources()
                if _value(r.type) in _HEALTH_RESOURCE_TYPES
            ],
            "habits": [
                serialize_habit(h) for h in application.list_habits()
            ],
        },
        "learning": {
            "latest_insight": (
                serialize_insight(insights[-1]) if insights else None
            ),
            "latest_reflection": (
                serialize_reflection(reflections[-1]) if reflections else None
            ),
            "last_studied": _iso(
                max(
                    (
                        k.last_revision
                        for k in knowledge
                        if k.last_revision is not None
                    ),
                    default=None,
                )
            ),
            "revised_today": sum(
                1
                for k in knowledge
                if k.last_revision is not None
                and k.last_revision.date() == now.date()
            ),
        },
        "system": {
            "scheduler": _value(application.scheduler_state()),
            "decision_engine": (
                "stateless (ready)" if status.is_operational else None
            ),
            "kernel": _value(status.state),
            "operational": status.is_operational,
            "snapshot_at": _iso(status.latest_snapshot_at),
            "daemon": None,  # the daemon wraps the Application; see report
        },
    }
