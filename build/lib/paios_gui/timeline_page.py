"""The Timeline page (M20): /plan entries joined with /events, bucketed.

Pure presentation over server decisions: the Scheduler planned the day
(GET /plan), the events carry their own status (GET /events); this page
only joins the two by event_id and sorts rows into display buckets. A
large NOW section leads — the running event with its elapsed progress
bar and the live countdown to the next planned start — followed by
Next, Upcoming, Ready, Completed today and Overdue. Bucketing takes
'now' as an explicit argument (the server's clock, fetched with the
data) so tests drive it with a fixed instant.

The live countdown is the shared CountdownLabel from widgets.py —
display sugar anchored to the server time of the last refresh. The
default Today view reads as one vertical flow: the NOW block (title,
time range, elapsed bar) and then the coming entries in start order,
visually connected. Rescheduling stays with the Scheduler — where
drag-and-drop would be expected, a visible note says who is in charge
instead of nothing.
"""

from datetime import datetime, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from paios_gui import format as fmt
from paios_gui import theme
from paios_gui.widgets import CountdownLabel, elapsed_percent

#: Event states that end the story (the History page's set).
TERMINAL_STATES = ("Completed", "Cancelled", "Archived", "Rejected", "Expired")
#: States meaning "running right now".
ACTIVE_STATES = ("Started", "Resumed")
#: The view selector's choices and their bucketing ranges.
VIEWS = ("Today", "Tomorrow", "Week", "Agenda")
#: Bucket keys -> section labels, in display order below NOW.
SECTIONS = (
    ("up_next", "Next"),
    ("upcoming", "Upcoming"),
    ("ready", "Ready"),
    ("completed_today", "Completed today"),
    ("overdue", "Overdue"),
)


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _in_view(start: datetime, now: datetime, view: str) -> bool:
    """Does a future planned_start fall inside the selected range?"""
    if view == "Tomorrow":
        return start.date() == (now + timedelta(days=1)).date()
    if view == "Week":
        return start.date() <= (now + timedelta(days=7)).date()
    if view == "Agenda":
        return True
    return start.date() == now.date()  # Today


def bucket_plan(
    entries: list[dict],
    events: list[dict],
    now: datetime,
    view: str = "Today",
) -> dict[str, list[dict]]:
    """Join plan entries with events and sort into display buckets.

    Pure function of its inputs — no clocks read here. Each returned
    row is {"entry": plan-entry-or-None, "event": event-or-None}.
    Keys: current, up_next, upcoming, ready, completed_today, overdue.
    """
    events_by_id = {event["event_id"]: event for event in events}
    planned_ids = {entry["event_id"] for entry in entries}
    buckets: dict[str, list[dict]] = {
        key: [] for key in (
            "current", "up_next", "upcoming", "ready",
            "completed_today", "overdue",
        )
    }

    for event in events:
        if event["status"] in ACTIVE_STATES:
            buckets["current"].append({"entry": None, "event": event})
        elif event["status"] == "Completed":
            ended = parse_iso(event.get("end_time"))
            if ended is not None and ended.date() == now.date():
                buckets["completed_today"].append(
                    {"entry": None, "event": event}
                )
        elif event["status"] == "Ready" and (
            event["event_id"] not in planned_ids
        ):
            # Planned Ready events are told by their plan entry
            # (Up next / Upcoming / Overdue), not twice.
            buckets["ready"].append({"entry": None, "event": event})

    future: list[dict] = []
    for entry in sorted(
        entries, key=lambda item: item.get("planned_start") or ""
    ):
        event = events_by_id.get(entry["event_id"])
        status = event["status"] if event is not None else None
        if status in ACTIVE_STATES or status in TERMINAL_STATES:
            continue  # already told in another bucket (or over)
        start = parse_iso(entry.get("planned_start"))
        end = parse_iso(entry.get("planned_end"))
        row = {"entry": entry, "event": event}
        if end is not None and end < now:
            buckets["overdue"].append(row)
        elif start is not None and start >= now and _in_view(
            start, now, view
        ):
            future.append(row)
    if future:
        buckets["up_next"].append(future[0])
        buckets["upcoming"].extend(future[1:])
    return buckets


class TimelinePage(QWidget):
    title = "Timeline"

    def __init__(self, window) -> None:
        super().__init__()
        self._window = window
        self._last_data: tuple | None = None
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        heading = QLabel("TIMELINE")
        heading.setObjectName("sectionTitle")
        header.addWidget(heading)
        self.view_box = QComboBox()
        self.view_box.addItems(VIEWS)
        self.view_box.currentTextChanged.connect(self._on_view_changed)
        header.addWidget(self.view_box)
        header.addStretch(1)
        layout.addLayout(header)

        # The NOW card: what is running, how far along, what's next.
        self.now_frame = QFrame()
        self.now_frame.setObjectName("nowCard")
        now_body = QVBoxLayout(self.now_frame)
        now_body.setContentsMargins(14, 10, 14, 12)
        now_title = QLabel("NOW")
        now_title.setObjectName("todayHeader")
        now_body.addWidget(now_title)
        self.now_body = now_body
        self._now_rows: list[QWidget] = []
        self.countdown_label = CountdownLabel(
            "Up next in ",
            empty_text="Nothing scheduled next.",
            zero_text="Up next: starting now",
        )
        now_body.addWidget(self.countdown_label)
        layout.addWidget(self.now_frame)

        self.empty_label = QLabel(
            "No plan yet. The Scheduler publishes one as intents are"
            " accepted — propose events from Planning or Events."
        )
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self._sections_layout = QVBoxLayout(container)
        self._sections_layout.addStretch(1)
        scroll.setWidget(container)
        layout.addWidget(scroll, stretch=1)

        self._section_frames: dict[str, tuple[QFrame, QVBoxLayout]] = {}
        for key, label in SECTIONS:
            frame = QFrame()
            frame.setObjectName("section")
            body = QVBoxLayout(frame)
            body.setContentsMargins(10, 8, 10, 10)
            title_label = QLabel(label.upper())
            title_label.setObjectName("sectionTitle")
            body.addWidget(title_label)
            frame.hide()
            self._section_frames[key] = (frame, body)
            self._sections_layout.insertWidget(
                self._sections_layout.count() - 1, frame
            )

        # A visible affordance where drag-and-drop would be expected.
        scheduler_note = QLabel(
            "Schedule is controlled by the PAIOS Scheduler —"
            " drag-and-drop rescheduling is not available; edit an"
            " event to change its intent."
        )
        scheduler_note.setObjectName("subtitle")
        scheduler_note.setWordWrap(True)
        layout.addWidget(scheduler_note)

    # --- data ------------------------------------------------------------

    def refresh(self, client) -> None:
        plan = client.get_plan()
        events = client.get_events()
        now_iso = client.get_dashboard()["current_time"]
        self.render(plan, events, now_iso)

    def _on_view_changed(self, _view: str) -> None:
        if self._last_data is not None:
            self.render(*self._last_data)

    def render(self, plan: dict, events: list[dict], now_iso: str) -> None:
        """Rebuild NOW and the sections from one consistent snapshot."""
        self._last_data = (plan, events, now_iso)
        now = parse_iso(now_iso) or datetime.now()
        buckets = bucket_plan(
            plan.get("entries") or [],
            events,
            now,
            self.view_box.currentText(),
        )
        up_next = buckets.get("up_next") or []
        self.countdown_label.set_target(
            parse_iso(up_next[0]["entry"].get("planned_start"))
            if up_next
            else None,
            now,
        )
        self._render_now(buckets["current"], now)

        any_rows = False
        for key, _label in SECTIONS:
            frame, body = self._section_frames[key]
            # Remove old row widgets (index 0 is the section title).
            while body.count() > 1:
                item = body.takeAt(1)
                widget = item.widget()
                if widget is not None:
                    widget.hide()
                    widget.setParent(None)
                    widget.deleteLater()
            rows = buckets[key]
            frame.setVisible(bool(rows))
            any_rows = any_rows or bool(rows)
            flowing = key in ("up_next", "upcoming")
            for index, row in enumerate(rows):
                if flowing and index:
                    # The vertical-flow connector: this happens, then
                    # that — the day reads top to bottom.
                    arrow = QLabel("↓")
                    arrow.setObjectName("subtitle")
                    arrow.setIndent(40)
                    body.addWidget(arrow)
                body.addWidget(self._build_row(key, row, now))
        self.empty_label.setVisible(
            not any_rows and not buckets["current"]
        )

    def _render_now(self, current: list[dict], now: datetime) -> None:
        for widget in self._now_rows:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        self._now_rows = []
        insert_at = 1  # after the NOW title, before the countdown
        if not current:
            idle = QLabel("Idle — nothing running.")
            idle.setObjectName("subtitle")
            self.now_body.insertWidget(insert_at, idle)
            self._now_rows.append(idle)
            return
        for row in current:
            event = row["event"]
            line = QWidget()
            line_layout = QHBoxLayout(line)
            line_layout.setContentsMargins(0, 2, 0, 2)
            time_label = QLabel(_time_range(event))
            time_label.setFixedWidth(96)
            line_layout.addWidget(time_label)
            title = QLabel(event["description"])
            title.setObjectName("cardTitle")
            line_layout.addWidget(title, stretch=1)
            chip = QLabel(event["status"])
            chip.setObjectName("statusChip")
            chip.setStyleSheet(
                f"color: {theme.BACKGROUND};"
                f" background: {theme.status_color(event['status'])};"
            )
            line_layout.addWidget(chip)
            percent = elapsed_percent(
                parse_iso(event.get("start_time")),
                event.get("duration_minutes"),
                now,
            )
            if percent is not None:
                bar = QProgressBar()
                bar.setRange(0, 100)
                bar.setValue(percent)
                bar.setFixedWidth(160)
                line_layout.addWidget(bar)
            self.now_body.insertWidget(insert_at, line)
            self._now_rows.append(line)
            insert_at += 1

    # --- row construction ---------------------------------------------------

    def _build_row(self, bucket: str, row: dict, now: datetime) -> QWidget:
        entry, event = row["entry"], row["event"]
        widget = QWidget()
        line = QHBoxLayout(widget)
        line.setContentsMargins(0, 2, 0, 2)

        start_iso = (
            entry.get("planned_start") if entry is not None
            else (event or {}).get("start_time")
        )
        end_iso = (
            entry.get("planned_end") if entry is not None
            else (event or {}).get("end_time")
        )
        time_label = QLabel(f"{fmt.clock(start_iso)}–{fmt.clock(end_iso)}")
        time_label.setFixedWidth(96)
        line.addWidget(time_label)

        title = (
            event["description"] if event is not None
            else (entry or {}).get("event_id") or "—"
        )
        title_label = QLabel(title)
        title_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        line.addWidget(title_label, stretch=1)

        status = event["status"] if event is not None else "Planned"
        chip = QLabel(status)
        chip.setObjectName("statusChip")
        chip.setStyleSheet(
            f"color: {theme.BACKGROUND};"
            f" background: {theme.status_color(status)};"
        )
        line.addWidget(chip)

        if bucket == "completed_today":
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(100)
            bar.setFixedWidth(120)
            line.addWidget(bar)
        return widget


def _time_range(event: dict) -> str:
    """HH:MM–HH:MM for a running event: recorded start, projected end
    (start + planned duration) while no end_time exists yet."""
    start = parse_iso(event.get("start_time"))
    end = parse_iso(event.get("end_time"))
    if end is None and start is not None and event.get("duration_minutes"):
        end = start + timedelta(minutes=event["duration_minutes"])
    return (
        f"{fmt.clock(event.get('start_time'))}"
        f"–{end.strftime('%H:%M') if end else '…'}"
    )
