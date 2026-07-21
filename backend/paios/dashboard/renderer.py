"""The renderer: facade queries in, one frame string out.

Every piece of data comes from the Application facade — read-only queries
only, never an action, never a component reach-through. Store-backed
queries (list_*) keep the dashboard live across processes; runtime views
(execution context, kernel state) are process-local by architecture and
are presented as such.

The optional daemon is duck-typed (`state`, `tick_count`, `last_tick_at`):
the daemon wraps the Application, so it can never be obtained *through*
the facade — an embedding process may hand its daemon in for display.
"""

from paios.dashboard import formatter, layout
from paios.dashboard.config import DashboardConfig


class DashboardRenderer:
    """Builds one complete dashboard frame from facade queries."""

    def __init__(self, application, config=None, daemon=None) -> None:
        self._app = application
        self._config = config if config is not None else DashboardConfig()
        self._daemon = daemon

    # --- frame -----------------------------------------------------------

    def render(self) -> str:
        sections = (
            ("CURRENT EVENT", self._current_event_lines()),
            ("CURRENT CONTEXT", self._current_context_lines()),
            ("RECOMMENDATIONS", self._recommendation_lines()),
            ("GOALS", self._goal_lines()),
            ("PROJECTS", self._project_lines()),
            ("TODAY", self._today_lines()),
            ("HEALTH", self._health_lines()),
            ("LEARNING", self._learning_lines()),
            ("SYSTEM", self._system_lines()),
        )
        return layout.compose(
            self._header_lines(), sections, self._config.width
        )

    # --- header ----------------------------------------------------------

    def _header_lines(self) -> list[str]:
        now = self._app.current_time()
        return [
            f"Current Time:  {formatter.clock_time(now)}",
            f"Daemon Status: {self._daemon_status()}",
        ]

    def _daemon_status(self) -> str:
        if self._daemon is None:
            return "Not attached (start PAIOS with an embedded daemon)"
        state = formatter.value(self._daemon.state)
        ticks = getattr(self._daemon, "tick_count", 0)
        last = formatter.clock_time(
            getattr(self._daemon, "last_tick_at", None)
        )
        return f"{state} — {ticks} tick(s), last at {last}"

    # --- sections --------------------------------------------------------

    def _current_event_lines(self) -> list[str]:
        running = [
            event
            for event in self._app.list_events()
            if formatter.is_running(event)
        ]
        if not running:
            return ["No running event."]
        event = running[0]
        now = self._app.current_time()
        duration = getattr(event.duration, "minutes", None)
        started = formatter.started_moment(event)
        elapsed = formatter.elapsed_minutes(started, now)
        remaining = formatter.remaining_minutes(started, duration, now)
        return [
            f"Event:     [{formatter.value(event.status)}] "
            f"{event.description}",
            f"Started:   {formatter.clock_time(started)}",
            "Duration:  "
            + (
                formatter.minutes_label(elapsed)
                if elapsed is not None
                else "-"
            )
            + (
                f" of {formatter.minutes_label(duration)}"
                if duration is not None
                else ""
            ),
            "Remaining: "
            + (
                formatter.minutes_label(remaining)
                if remaining is not None
                else "-"
            ),
        ]

    def _current_context_lines(self) -> list[str]:
        snapshot = self._app.snapshot()
        lines: list[str] = []
        if snapshot is None:
            lines.append("Execution Context: -")
        else:
            context = snapshot.execution_context
            kind = type(context).__name__
            detail = ""
            if hasattr(context, "reason"):
                detail = f" ({formatter.value(context.reason)})"
            lines.append(
                f"Execution Context: {kind}{detail} "
                f"since {formatter.short_time(context.since)}"
            )
            window = snapshot.running_context_window
            lines.append(
                "Context Window:    "
                + (
                    f"{window.window_id} "
                    f"[{formatter.value(window.current_state)}]"
                    if window is not None
                    else "-"
                )
            )
        disturbers = self._app.active_event_disturbers()
        if disturbers:
            lines.append("Active Disturbers:")
            lines.extend(
                "  " + formatter.disturber_line(disturber)
                for disturber in disturbers[: self._config.max_rows_per_section]
            )
        else:
            lines.append("Active Disturbers: none")
        return lines

    def _recommendation_lines(self) -> list[str]:
        recommendations = self._app.active_recommendations()
        if not recommendations:
            return ["No active recommendations."]
        return [
            f"{index}. {formatter.recommendation_line(recommendation)}"
            for index, recommendation in enumerate(
                recommendations[: self._config.max_rows_per_section], start=1
            )
        ]

    def _goal_lines(self) -> list[str]:
        goals = self._app.list_goals()
        if not goals:
            return ["No goals."]
        # Active goals first — display ordering, nothing more.
        ordered = [g for g in goals if formatter.value(g.status) == "Active"]
        ordered.extend(
            g for g in goals if formatter.value(g.status) != "Active"
        )
        shown = ordered[: self._config.max_rows_per_section]
        lines = [formatter.goal_line(goal) for goal in shown]
        if len(goals) > len(shown):
            lines.append(f"(+{len(goals) - len(shown)} more)")
        return lines

    def _project_lines(self) -> list[str]:
        projects = self._app.list_projects()
        if not projects:
            return ["No projects."]
        lines = []
        for project in projects[: self._config.max_rows_per_section]:
            progress = self._app.get_project_progress(project.project_id)
            bar = (
                formatter.progress_bar(progress.completion_percentage)
                if progress is not None
                else "-"
            )
            lines.append(
                f"[{formatter.value(project.status)}] {project.name}"
            )
            lines.append(f"  {bar}")
        if len(projects) > self._config.max_rows_per_section:
            lines.append(
                f"(+{len(projects) - self._config.max_rows_per_section} more)"
            )
        return lines

    def _today_lines(self) -> list[str]:
        now = self._app.current_time()
        events = self._app.list_events()
        completed_today = [
            event
            for event in events
            if formatter.is_completed(event)
            and formatter.same_day(event.end_time or event.start_time, now)
        ]
        running = [event for event in events if formatter.is_running(event)]
        upcoming = [event for event in events if formatter.is_upcoming(event)]
        lines = [f"Completed: {len(completed_today)}"]
        lines.extend(
            "  " + formatter.event_line(event)
            for event in completed_today[: self._config.max_rows_per_section]
        )
        lines.append(f"Running:   {len(running)}")
        lines.extend(
            "  " + formatter.event_line(event)
            for event in running[: self._config.max_rows_per_section]
        )
        lines.append(f"Upcoming:  {len(upcoming)}")
        lines.extend(
            "  " + formatter.event_line(event)
            for event in upcoming[: self._config.max_rows_per_section]
        )
        return lines

    def _health_lines(self) -> list[str]:
        """Health-related state that EXISTS in the domain today: HEALTH-
        adjacent Resources and Learning-detected Habits (the mission's
        Smoking / Medication / Exercise examples live here once tracked
        as Habits)."""
        lines: list[str] = []
        for resource in self._app.list_resources():
            if formatter.value(resource.type) in (
                "Health",
                "Energy",
                "Stress",
            ):
                lines.append(
                    f"{formatter.value(resource.type)}: "
                    f"{resource.current_value:g} {resource.unit}"
                )
        habits = self._app.list_habits()
        for habit in habits[: self._config.max_rows_per_section]:
            trend = (
                f", trend {habit.current_trend}"
                if getattr(habit, "current_trend", None)
                else ""
            )
            lines.append(
                f"Habit: {habit.name} "
                f"(strength {habit.strength:g}{trend})"
            )
        return lines or ["No health data tracked yet."]

    def _learning_lines(self) -> list[str]:
        insights = self._app.list_insights()
        reflections = self._app.list_reflections()
        knowledge = self._app.list_knowledge()
        now = self._app.current_time()
        latest_insight = (
            f"[{insights[-1].category or 'uncategorized'}] "
            f"from {formatter.day(insights[-1].created_at)}"
            if insights
            else "-"
        )
        latest_reflection = "-"
        if reflections:
            last = reflections[-1]
            latest_reflection = (
                last.lesson_learned
                or last.interpretation
                or f"recorded {formatter.day(last.created_at)}"
            )
        revised_today = sum(
            1
            for item in knowledge
            if formatter.same_day(item.last_revision, now)
        )
        last_studied = max(
            (
                item.last_revision
                for item in knowledge
                if item.last_revision is not None
            ),
            default=None,
        )
        return [
            f"Latest Insight:    {latest_insight}",
            f"Latest Reflection: {latest_reflection}",
            f"Study:             last {formatter.day(last_studied)}, "
            f"{revised_today} revised today",
        ]

    def _system_lines(self) -> list[str]:
        status = self._app.status()
        scheduler = formatter.value(self._app.scheduler_state())
        operational = "yes" if status.is_operational else "no"
        return [
            f"Scheduler:       {scheduler}",
            "Decision Engine: stateless (ready)"
            if status.is_operational
            else "Decision Engine: -",
            f"Kernel:          {formatter.value(status.state)} "
            f"(operational: {operational})",
            f"Snapshot:        "
            f"{formatter.clock_time(status.latest_snapshot_at)}",
            f"Daemon:          {self._daemon_status()}",
        ]
