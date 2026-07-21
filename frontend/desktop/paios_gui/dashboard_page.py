"""The TODAY dashboard: every mission section, filled from REST data.

The page renders three GET responses (/dashboard, /resources,
/reflections) and never computes anything the API did not send — counts,
groupings and timing all arrive in the payload. Buttons delegate to the
window's ``run_action`` which performs exactly one REST call.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from paios_gui import format as fmt
from paios_gui.dialogs import DisturberDialog, OutcomeDialog, ReasonDialog
from paios_gui.widgets import NoticeLog, Section

_MAX_ROWS = 5


class DashboardPage(QWidget):
    def __init__(self, window) -> None:
        super().__init__()
        self._window = window

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        header = QLabel("TODAY")
        header.setObjectName("todayHeader")
        header.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(header)

        self.sections: dict[str, Section] = {}
        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)

        order = (
            "Time", "Status",
            "Current Event", "Current Context",
            "Today's Goals", "Today's Projects",
            "Recommendations", "Deep Work",
            "Health", "Resources",
            "Study", "Learning",
            "Recent Reflections", "Disturbers",
        )
        for index, title in enumerate(order):
            section = Section(title)
            self.sections[title] = section
            grid.addWidget(section, index // 2, index % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        # Interactive extras inside their sections.
        self._event_buttons = _ButtonRow(
            ("Pause", "Complete", "Cancel"), self._on_event_action
        )
        self._event_buttons.setVisible(False)  # until a running event shows
        self.sections["Current Event"].body_layout.addWidget(
            self._event_buttons
        )
        self._recommendation_rows = QVBoxLayout()
        self.sections["Recommendations"].body_layout.addLayout(
            self._recommendation_rows
        )
        report_button = QPushButton("Report disturbance…")
        report_button.clicked.connect(self._on_report_disturber)
        self.sections["Disturbers"].body_layout.addWidget(report_button)

        notifications = Section("Notifications")
        self.notice_log = NoticeLog()
        self.notice_log.setMaximumHeight(120)
        notifications.body_layout.addWidget(self.notice_log)
        grid.addWidget(notifications, len(order) // 2, 0, 1, 2)
        self.sections["Notifications"] = notifications

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(grid_host)
        root.addWidget(scroll, stretch=1)

        self.footer = QLabel("")
        self.footer.setObjectName("footer")
        root.addWidget(self.footer)

        self._current_event_id: str | None = None

    # --- rendering -------------------------------------------------------

    def update_data(
        self, dashboard: dict, resources: list, reflections: list
    ) -> None:
        s = self.sections
        s["Time"].set_lines([f"Current time: {fmt.day_time(dashboard['current_time'])}"])
        s["Status"].set_lines(_status_lines(dashboard["system"]))

        event = dashboard.get("current_event")
        self._current_event_id = event["event_id"] if event else None
        s["Current Event"].set_lines(_current_event_lines(event))
        self._event_buttons.setVisible(event is not None)

        s["Current Context"].set_lines(
            _context_lines(dashboard.get("current_context"))
        )
        s["Today's Goals"].set_lines(_goal_lines(dashboard["goals"]))
        s["Today's Projects"].set_lines(_project_lines(dashboard["projects"]))
        self._render_recommendations(dashboard["recommendations"])
        s["Deep Work"].set_lines(_deep_work_lines(dashboard["today"]))
        s["Health"].set_lines(_health_lines(dashboard["health"]))
        s["Resources"].set_lines(_resource_lines(resources))
        s["Study"].set_lines(_study_lines(dashboard["learning"]))
        s["Learning"].set_lines(_learning_lines(dashboard["learning"]))
        s["Recent Reflections"].set_lines(_reflection_lines(reflections))
        s["Disturbers"].set_lines(
            _disturber_lines(dashboard["active_disturbers"])
        )

    def set_footer(self, text: str) -> None:
        self.footer.setText(text)

    def _render_recommendations(self, recommendations: list) -> None:
        while self._recommendation_rows.count():
            item = self._recommendation_rows.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self.sections["Recommendations"].set_lines(
            [] if recommendations else ["No active recommendations."]
        )
        for recommendation in recommendations[:_MAX_ROWS]:
            self._recommendation_rows.addWidget(
                _RecommendationRow(recommendation, self._window)
            )

    # --- actions (each: one REST call via the window) --------------------

    def _on_event_action(self, label: str) -> None:
        event_id = self._current_event_id
        if event_id is None:
            return
        window, client = self._window, self._window.client
        if label == "Pause":
            window.run_action(
                lambda: client.pause_event(event_id), "Event paused"
            )
        elif label == "Complete":
            dialog = OutcomeDialog(self)
            if dialog.exec():
                outcome = dialog.values()["actual_outcome"]
                window.run_action(
                    lambda: client.complete_event(event_id, outcome),
                    "Event completed",
                )
        elif label == "Cancel":
            dialog = ReasonDialog("Cancel event", "Reason (optional)", self)
            if dialog.exec():
                reason = dialog.values()["reason"]
                window.run_action(
                    lambda: client.cancel_event(event_id, reason),
                    "Event cancelled",
                )

    def _on_report_disturber(self) -> None:
        dialog = DisturberDialog(self)
        if dialog.exec():
            values = dialog.values()
            self._window.run_action(
                lambda: self._window.client.report_disturber(**values),
                "Disturbance reported",
            )


class _ButtonRow(QWidget):
    def __init__(self, labels: tuple[str, ...], on_click) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        for label in labels:
            button = QPushButton(label)
            button.clicked.connect(
                lambda _=False, text=label: on_click(text)
            )
            layout.addWidget(button)
        layout.addStretch(1)


class _RecommendationRow(QWidget):
    def __init__(self, recommendation: dict, window) -> None:
        super().__init__()
        rec_id = recommendation["recommendation_id"]
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        text = QLabel(
            f"{recommendation['reason']}  "
            f"(priority {recommendation['priority']:.2f}, "
            f"expires {fmt.clock(recommendation['expires_at'])})"
        )
        text.setWordWrap(True)
        layout.addWidget(text, stretch=1)
        accept = QPushButton("Accept")
        accept.clicked.connect(
            lambda: window.run_action(
                lambda: window.client.accept_recommendation(rec_id),
                "Recommendation accepted",
            )
        )
        layout.addWidget(accept)
        reject = QPushButton("Reject")
        reject.clicked.connect(lambda: self._reject(window, rec_id))
        layout.addWidget(reject)

    def _reject(self, window, rec_id: str) -> None:
        dialog = ReasonDialog(
            "Reject recommendation", "Reason (optional)", self
        )
        if dialog.exec():
            reason = dialog.values()["reason"]
            window.run_action(
                lambda: window.client.reject_recommendation(rec_id, reason),
                "Recommendation rejected",
            )


# --- pure line builders (REST payload -> display strings) -----------------


def _status_lines(system: dict) -> list[str]:
    return [
        f"Kernel: {fmt.text_or_dash(system['kernel'])}"
        f"   Scheduler: {fmt.text_or_dash(system['scheduler'])}",
        f"Operational: {'yes' if system['operational'] else 'NO'}"
        f"   Decision engine: {fmt.text_or_dash(system['decision_engine'])}",
        f"Last snapshot: {fmt.day_time(system['snapshot_at'])}",
    ]


def _current_event_lines(event: dict | None) -> list[str]:
    if event is None:
        return ["Idle — no running event."]
    return [
        f"[{event['status']}] {event['description']}",
        f"Started {fmt.clock(event['started_at'])}"
        f" · elapsed {fmt.minutes(event['elapsed_minutes'])}"
        f" · remaining {fmt.minutes(event['remaining_minutes'])}",
    ]


def _context_lines(context: dict | None) -> list[str]:
    if context is None:
        return ["No snapshot yet."]
    window = context.get("context_window")
    lines = [
        f"{context['execution_context']}"
        + (f" — {context['reason']}" if context.get("reason") else ""),
        f"Since {fmt.day_time(context['since'])}",
    ]
    if window is not None:
        lines.append(
            f"Context window {window['window_id'][:8]}… [{window['state']}]"
        )
    return lines


def _goal_lines(goals: list) -> list[str]:
    if not goals:
        return ["No goals."]
    active = [g for g in goals if g["status"] == "Active"]
    others = [g for g in goals if g["status"] != "Active"]
    return [
        f"[{goal['status']}] {goal['name']}"
        for goal in (active + others)[:_MAX_ROWS]
    ] + ([f"(+{len(goals) - _MAX_ROWS} more)"] if len(goals) > _MAX_ROWS else [])


def _project_lines(projects: list) -> list[str]:
    if not projects:
        return ["No projects."]
    lines = []
    for project in projects[:_MAX_ROWS]:
        progress = project.get("progress")
        suffix = (
            f" — {fmt.percent(progress['completion_percentage'])}"
            if progress
            else ""
        )
        lines.append(f"[{project['status']}] {project['name']}{suffix}")
    return lines


def _deep_work_lines(today: dict) -> list[str]:
    lines = [
        f"Completed today: {len(today['completed'])}"
        f"   Running: {len(today['running'])}"
        f"   Upcoming: {len(today['upcoming'])}"
    ]
    for event in (today["running"] + today["upcoming"])[:_MAX_ROWS]:
        duration = event.get("duration_minutes")
        lines.append(
            f"[{event['status']}] {event['description']}"
            + (f" ({fmt.minutes(duration)})" if duration is not None else "")
        )
    return lines


def _health_lines(health: dict) -> list[str]:
    lines = [
        f"{resource['type']}: {resource['current_value']:g} {resource['unit']}"
        for resource in health["resources"]
    ] or ["No health resources tracked."]
    for habit in health["habits"][:3]:
        lines.append(
            f"Habit: {habit['name']} ({habit['current_trend']},"
            f" strength {habit['strength']:.2f})"
        )
    return lines


def _resource_lines(resources: list) -> list[str]:
    if not resources:
        return ["No resources."]
    return [
        f"{resource['type']}: {resource['current_value']:g} {resource['unit']}"
        f"  (updated {fmt.day_time(resource['last_updated'])})"
        for resource in resources[:_MAX_ROWS + 2]
    ]


def _study_lines(learning: dict) -> list[str]:
    return [
        f"Last studied: {fmt.day_time(learning['last_studied'])}",
        f"Revised today: {learning['revised_today']}",
    ]


def _learning_lines(learning: dict) -> list[str]:
    insight = learning.get("latest_insight")
    if insight is None:
        return ["No insights yet."]
    return [
        f"Latest insight: [{insight['category']}]"
        f" confidence {insight['confidence']:.2f}"
        f" ({fmt.day_time(insight['created_at'])})",
        f"Reusable: {'yes' if insight['reusable'] else 'no'}",
    ]


def _reflection_lines(reflections: list) -> list[str]:
    if not reflections:
        return ["No reflections yet."]
    lines = []
    for reflection in reflections[-3:][::-1]:
        summary = (
            reflection.get("lesson_learned")
            or reflection.get("facts")
            or "(no text)"
        )
        lines.append(
            f"{fmt.day_time(reflection['created_at'])} — {summary}"
        )
    return lines


def _disturber_lines(disturbers: list) -> list[str]:
    if not disturbers:
        return ["No active disturbers."]
    return [
        f"[{disturber['severity']}] {disturber['type']}:"
        f" {disturber['description']} ({disturber['state']})"
        for disturber in disturbers[:_MAX_ROWS]
    ]
