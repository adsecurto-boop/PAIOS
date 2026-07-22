"""The Planning page (M20): the Today Home — a conversation, not a form.

The landing experience: a time-of-day greeting, a Today's Focus card
(the running event with its elapsed bar, else the next planned entry
with a live countdown — the shared CountdownLabel), and a Next line
whose "Recommended because:" bullets come from POST
/assistant/explain-day's deterministic reasons. All of it presentation
over server decisions; 'now' is injectable for tests.

Below that, one large capture box ("What do you want to accomplish
today?") and one prominent action: Plan it (Ctrl+Enter). The
assistant's classification comes back as preview CARDS — each editable
(kind, priority, estimated duration), each showing the server's "why"
and any clarification question inline. Approve plan then executes ONLY
the checked cards through the ordinary endpoints — goal -> POST
/goals, project -> POST /projects, event -> POST /events (priority in
the body, duration as metadata), inbox -> POST /inbox. Nothing is
created until Approve; the assistant proposes, the user disposes.

Two more day-level actions live here: Explain My Schedule (POST
/assistant/explain-day, reasons shown verbatim) and Review Today — a
presentation-only summary composed from GET /dashboard + GET /events
(completed today / overdue / still upcoming); no new endpoint, no
decisions made client-side.
"""

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from paios_gui import format as fmt
from paios_gui.timeline_page import bucket_plan, parse_iso
from paios_gui.widgets import CountdownLabel, elapsed_percent

#: The kinds a preview card may be applied as (the combo's choices).
KINDS = ("goal", "project", "event", "inbox")
#: Event states that end the story (mirrors the History page's set).
_TERMINAL = ("Completed", "Cancelled", "Archived", "Rejected", "Expired")
_ACTIVE = ("Started", "Resumed")


def greeting(now: datetime | None = None) -> str:
    """Time-of-day wording from the LOCAL clock — pure presentation;
    tests inject the instant."""
    hour = (now if now is not None else datetime.now()).hour
    if hour < 12:
        return "Good Morning."
    if hour < 18:
        return "Good Afternoon."
    return "Good Evening."


class ProposalCard(QFrame):
    """One classified capture: editable kind/priority/duration plus the
    assistant's why and question — approval is the checkbox."""

    def __init__(self, item: dict, question: str | None = None) -> None:
        super().__init__()
        self.setObjectName("card")
        self.item = item
        body = QVBoxLayout(self)
        body.setContentsMargins(12, 8, 12, 8)

        top = QHBoxLayout()
        self.include = QCheckBox(item.get("text") or "")
        # Duplicates default to excluded — applying them would recreate
        # something the server says already exists.
        self.include.setChecked(not item.get("duplicate_of"))
        top.addWidget(self.include, stretch=1)
        body.addLayout(top)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Kind:"))
        self.kind_box = QComboBox()
        self.kind_box.addItems(KINDS)
        if item.get("kind") in KINDS:
            self.kind_box.setCurrentText(item["kind"])
        controls.addWidget(self.kind_box)
        controls.addWidget(QLabel("Priority:"))
        self.priority = QDoubleSpinBox()
        self.priority.setRange(0.0, 100.0)
        self.priority.setSpecialValueText("(default)")
        controls.addWidget(self.priority)
        controls.addWidget(QLabel("Duration:"))
        self.duration = QSpinBox()
        self.duration.setRange(0, 1440)
        self.duration.setSuffix(" min")
        self.duration.setSpecialValueText("(unset)")
        controls.addWidget(self.duration)
        controls.addStretch(1)
        body.addLayout(controls)

        why_parts = []
        if item.get("duplicate_of"):
            why_parts.append(f"Duplicate of: {item['duplicate_of']}")
        if item.get("notes"):
            why_parts.append(item["notes"])
        if why_parts:
            why = QLabel(" · ".join(why_parts))
            why.setObjectName("cardWhy")
            why.setWordWrap(True)
            body.addWidget(why)
        self.question_label = None
        if question:
            self.question_label = QLabel(f"? {question}")
            self.question_label.setWordWrap(True)
            body.addWidget(self.question_label)

    def values(self) -> dict:
        """What Approve sends for this card (when checked)."""
        return {
            "title": self.item.get("title") or self.item.get("text") or "",
            "kind": self.kind_box.currentText(),
            "priority": self.priority.value() or None,
            "duration_minutes": self.duration.value() or None,
        }


def _reason_for(explanation: dict | None, event_id: str) -> str | None:
    """The explain-day reason recorded for one plan entry, if any."""
    if not explanation:
        return None
    for entry in explanation.get("entries") or []:
        if entry.get("event_id") == event_id:
            return entry.get("reason") or None
    return None


class PlanningPage(QWidget):
    title = "Planning"

    def __init__(self, window) -> None:
        super().__init__()
        self._window = window
        self.cards: list[ProposalCard] = []
        self._explained_for: tuple = ()
        self._explanation_cache: dict | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 16, 48, 8)

        # --- the Today Home header -------------------------------------
        self.greeting_label = QLabel(greeting())
        self.greeting_label.setObjectName("todayHeader")
        self.greeting_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.greeting_label)

        self.focus_frame = QFrame()
        self.focus_frame.setObjectName("nowCard")
        focus_body = QVBoxLayout(self.focus_frame)
        focus_body.setContentsMargins(14, 8, 14, 10)
        focus_heading = QLabel("TODAY'S FOCUS")
        focus_heading.setObjectName("sectionTitle")
        focus_body.addWidget(focus_heading)
        focus_row = QHBoxLayout()
        self.focus_label = QLabel("")
        self.focus_label.setObjectName("cardTitle")
        focus_row.addWidget(self.focus_label)
        self.focus_countdown = CountdownLabel(
            "starts in ", zero_text="starting now", minutes=True
        )
        self.focus_countdown.setObjectName("cardTitle")
        focus_row.addWidget(self.focus_countdown)
        self.focus_progress = QProgressBar()
        self.focus_progress.setRange(0, 100)
        self.focus_progress.setFixedWidth(200)
        self.focus_progress.hide()
        focus_row.addWidget(self.focus_progress)
        focus_row.addStretch(1)
        focus_body.addLayout(focus_row)
        self.next_label = QLabel("")
        self.next_label.hide()
        focus_body.addWidget(self.next_label)
        self.next_reasons = QLabel("")
        self.next_reasons.setObjectName("cardWhy")
        self.next_reasons.setWordWrap(True)
        self.next_reasons.hide()
        focus_body.addWidget(self.next_reasons)
        layout.addWidget(self.focus_frame)

        subtitle = QLabel(
            "Brain-dump your day — one thought per line. Day headers"
            " like 'Tomorrow' are understood."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(subtitle)

        self.capture = QPlainTextEdit()
        self.capture.setObjectName("captureBox")
        self.capture.setPlaceholderText(
            "What do you want to accomplish today?"
        )
        self.capture.setMinimumHeight(110)
        self.capture.setMaximumHeight(160)
        layout.addWidget(self.capture)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.propose_button = QPushButton("Plan it")
        self.propose_button.setObjectName("primaryAction")
        self.propose_button.setToolTip("Ctrl+Enter")
        self.propose_button.clicked.connect(self.propose)
        buttons.addWidget(self.propose_button)
        self.explain_button = QPushButton("Explain My Schedule")
        self.explain_button.clicked.connect(self.explain_day)
        buttons.addWidget(self.explain_button)
        self.review_button = QPushButton("Review Today")
        self.review_button.clicked.connect(self.review_today)
        buttons.addWidget(self.review_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        for keys in ("Ctrl+Return", "Ctrl+Enter"):
            shortcut = QShortcut(QKeySequence(keys), self.capture)
            shortcut.setContext(
                Qt.ShortcutContext.WidgetWithChildrenShortcut
            )
            shortcut.activated.connect(self.propose)

        self.working_label = QLabel("")
        self.working_label.setObjectName("working")
        self.working_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.working_label.hide()
        layout.addWidget(self.working_label)

        self.empty_label = QLabel(
            "Nothing captured yet — type above to brain-dump, then"
            " press Plan it."
        )
        self.empty_label.setObjectName("subtitle")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.empty_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self.cards_layout = QVBoxLayout(container)
        self.cards_layout.addStretch(1)
        scroll.setWidget(container)
        layout.addWidget(scroll, stretch=1)

        approve_row = QHBoxLayout()
        approve_row.addStretch(1)
        self.apply_button = QPushButton("Approve plan")
        self.apply_button.setObjectName("primaryAction")
        self.apply_button.clicked.connect(self.apply)
        self.apply_button.hide()
        approve_row.addWidget(self.apply_button)
        approve_row.addStretch(1)
        layout.addLayout(approve_row)

        self.questions_label = QLabel("")
        self.questions_label.setWordWrap(True)
        self.questions_label.hide()
        layout.addWidget(self.questions_label)

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

    # --- the poll cycle ----------------------------------------------------

    def refresh(self, client) -> None:
        """Pull the Today Home header's data; the capture/proposal flow
        below stays interaction-driven."""
        plan = client.get_plan()
        events = client.get_events()
        now_iso = client.get_dashboard()["current_time"]
        self.update_home(
            plan, events, now_iso, self._explanation_for(client, plan)
        )

    def _explanation_for(self, client, plan: dict) -> dict | None:
        """Explain-day reasons, re-fetched only when the plan changes —
        best effort: no reasons is a state, not an error."""
        ids = tuple(
            entry["event_id"] for entry in plan.get("entries") or []
        )
        if ids == self._explained_for:
            return self._explanation_cache
        self._explained_for = ids
        if not ids:
            self._explanation_cache = None
            return None
        try:
            self._explanation_cache = (
                self._window.client.assistant_explain_day()
            )
        except Exception:
            self._explanation_cache = None
        return self._explanation_cache

    def update_home(
        self,
        plan: dict,
        events: list[dict],
        now_iso: str,
        explanation: dict | None = None,
        local_now: datetime | None = None,
    ) -> None:
        """Render greeting, Today's Focus and Next (the test seam).

        The greeting follows the LOCAL clock (injectable); focus/next
        follow the server clock that came with the data."""
        self.greeting_label.setText(greeting(local_now))
        now = parse_iso(now_iso) or datetime.now()
        buckets = bucket_plan(
            plan.get("entries") or [], events, now, "Agenda"
        )
        future = buckets["up_next"] + buckets["upcoming"]
        running = buckets["current"]

        if running:
            event = running[0]["event"]
            self.focus_label.setText(event["description"])
            self.focus_countdown.set_target(None, None)
            self.focus_countdown.hide()
            percent = elapsed_percent(
                parse_iso(event.get("start_time")),
                event.get("duration_minutes"),
                now,
            )
            self.focus_progress.setVisible(percent is not None)
            if percent is not None:
                self.focus_progress.setValue(percent)
            next_row = future[0] if future else None
        elif future:
            entry, event = future[0]["entry"], future[0]["event"]
            title = (
                event["description"] if event else entry["event_id"]
            )
            self.focus_label.setText(f"{title} —")
            self.focus_countdown.show()
            self.focus_countdown.set_target(
                parse_iso(entry.get("planned_start")), now
            )
            self.focus_progress.hide()
            next_row = future[1] if len(future) > 1 else None
        else:
            self.focus_label.setText(
                "Nothing scheduled yet — plan your day below."
            )
            self.focus_countdown.set_target(None, None)
            self.focus_countdown.hide()
            self.focus_progress.hide()
            next_row = None

        if next_row is None:
            self.next_label.hide()
            self.next_reasons.hide()
            return
        entry, event = next_row["entry"], next_row["event"]
        title = event["description"] if event else entry["event_id"]
        self.next_label.setText(
            f"Next: {fmt.clock(entry.get('planned_start'))}  {title}"
        )
        self.next_label.show()
        reason = _reason_for(explanation, entry["event_id"])
        if reason:
            bullets = "\n".join(
                f"  • {part}" for part in reason.split("; ") if part
            )
            self.next_reasons.setText(
                "Recommended because:\n" + bullets
            )
            self.next_reasons.show()
        else:
            self.next_reasons.hide()

    def showEvent(self, event) -> None:  # Qt naming
        """Landing on Planning puts the caret in the capture box —
        typing is the page's primary action."""
        super().showEvent(event)
        self.capture.setFocus()

    # --- busy indicator (polish) ---------------------------------------------

    def _working(self, text: str) -> None:
        self.working_label.setText(text)
        self.working_label.setVisible(bool(text))
        self.working_label.repaint()

    # --- propose ------------------------------------------------------------

    def propose(self) -> None:
        text = self.capture.toPlainText().strip()
        if not text:
            self._window.notify("Type some captures first.", "warn")
            return
        self._working("Working… asking the planner")
        try:
            proposal = self._window.client.assistant_plan(text)
        except Exception as error:
            self._window.notify(f"Proposal failed: {error}", "error")
            return
        finally:
            self._working("")
        self.show_proposal(proposal)
        self._window.notify(
            f"Proposal ready ({proposal.get('source', '?')}):"
            f" {len(self.cards)} item(s)",
            "ok",
        )

    def _clear_cards(self) -> None:
        for card in self.cards:
            card.hide()
            card.setParent(None)
            card.deleteLater()
        self.cards = []

    def show_proposal(self, proposal: dict) -> None:
        """Render items as editable cards (also the test seam)."""
        self._clear_cards()
        items = list(proposal.get("items") or [])
        questions = list(proposal.get("questions") or [])
        unattached = []
        # Attach each question to the card whose text it mentions;
        # anything unmatched is shown below the cards.
        per_item: dict[int, str] = {}
        for question in questions:
            lowered = question.lower()
            for index, item in enumerate(items):
                text = (item.get("text") or "").lower()
                if text and text in lowered and index not in per_item:
                    per_item[index] = question
                    break
            else:
                unattached.append(question)
        for index, item in enumerate(items):
            card = ProposalCard(item, per_item.get(index))
            self.cards.append(card)
            self.cards_layout.insertWidget(
                self.cards_layout.count() - 1, card
            )
        self.empty_label.setVisible(not items)
        self.apply_button.setVisible(bool(items))
        self.questions_label.setVisible(bool(unattached))
        self.questions_label.setText(
            "Clarification needed:\n"
            + "\n".join(f"  • {question}" for question in unattached)
        )
        self.summary_label.setText("")

    # --- approve -------------------------------------------------------------

    def checked_cards(self) -> list[ProposalCard]:
        return [
            card
            for card in self.cards
            if getattr(card, "include", None) is not None
            and card.include.isChecked()
        ]

    def apply(self) -> None:
        """One ordinary REST call per checked card; a summary at the end."""
        client = self._window.client
        created: list[str] = []
        failures: list[str] = []
        self._working("Working… creating items")
        for card in self.checked_cards():
            values = card.values()
            title, kind = values["title"], values["kind"]
            try:
                if kind == "goal":
                    client.create_goal(title)
                elif kind == "project":
                    client.create_project(title)
                elif kind == "event":
                    metadata = None
                    if values["duration_minutes"]:
                        metadata = {
                            "estimated_duration_minutes": values[
                                "duration_minutes"
                            ]
                        }
                    client.create_event(
                        title,
                        priority=values["priority"],
                        metadata=metadata,
                    )
                else:
                    client.add_inbox(title)
                created.append(f"{kind}: {title}")
            except Exception as error:
                failures.append(f"{kind}: {title} — {error}")
        self._working("")
        summary = f"Applied {len(created)} item(s)."
        if created:
            summary += "\n" + "\n".join(f"  ✓ {line}" for line in created)
        if failures:
            summary += "\n" + "\n".join(f"  ✗ {line}" for line in failures)
        self.summary_label.setText(summary)
        self._window.notify(
            f"Plan applied: {len(created)} created,"
            f" {len(failures)} failed",
            "error" if failures else "ok",
        )
        self._window.refresh_now()

    # --- explain my schedule ---------------------------------------------------

    def explain_day(self) -> None:
        self._working("Working… asking for reasons")
        try:
            explanation = self._window.client.assistant_explain_day()
        except Exception as error:
            self._window.notify(f"Explain failed: {error}", "error")
            return
        finally:
            self._working("")
        self.show_explanation(explanation)

    def show_explanation(self, explanation: dict) -> None:
        self._clear_cards()
        self.apply_button.hide()
        entries = list(explanation.get("entries") or [])
        for entry in entries:
            card = QFrame()
            card.setObjectName("card")
            body = QVBoxLayout(card)
            body.setContentsMargins(12, 8, 12, 8)
            start = (entry.get("planned_start") or "")[11:16]
            title = QLabel(
                f"{start} — {entry.get('title') or entry.get('event_id')}"
                f" ({entry.get('duration_minutes', '—')} min)"
            )
            title.setObjectName("cardTitle")
            body.addWidget(title)
            why = QLabel(entry.get("reason") or "—")
            why.setObjectName("cardWhy")
            why.setWordWrap(True)
            body.addWidget(why)
            self.cards.append(card)  # type: ignore[arg-type]
            self.cards_layout.insertWidget(
                self.cards_layout.count() - 1, card
            )
        self.empty_label.setVisible(not entries)
        answer = explanation.get("answer")
        if not entries:
            self.summary_label.setText(
                "Nothing planned for today yet — the day explains itself."
            )
        elif answer:
            self.summary_label.setText(answer)
        else:
            self.summary_label.setText(
                f"Today's plan: {len(entries)} entr"
                + ("y" if len(entries) == 1 else "ies")
                + f" ({explanation.get('source', '?')})."
            )

    # --- review today (presentation-only composition) ---------------------------

    def review_today(self) -> None:
        self._working("Working… gathering today")
        try:
            dashboard = self._window.client.get_dashboard()
            events = self._window.client.get_events()
        except Exception as error:
            self._window.notify(f"Review failed: {error}", "error")
            return
        finally:
            self._working("")
        self.show_review(dashboard, events)

    def show_review(self, dashboard: dict, events: list[dict]) -> None:
        """Compose completed/overdue/upcoming from data the server
        already decided — grouping by timestamps is display, not logic."""
        self._clear_cards()
        self.apply_button.hide()
        now_iso = dashboard.get("current_time") or ""
        today = now_iso[:10]
        completed = [
            event for event in events
            if event["status"] == "Completed"
            and (event.get("end_time") or "")[:10] == today
        ]
        overdue = [
            event for event in events
            if event["status"] not in _TERMINAL + _ACTIVE
            and event.get("start_time")
            and event["start_time"] < now_iso
        ]
        upcoming = [
            event for event in events
            if event["status"] not in _TERMINAL + _ACTIVE
            and (
                not event.get("start_time")
                or event["start_time"] >= now_iso
            )
        ]
        groups = (
            (f"Completed today ({len(completed)})", completed),
            (f"Overdue ({len(overdue)})", overdue),
            (f"Still upcoming ({len(upcoming)})", upcoming),
        )
        for label, group in groups:
            card = QFrame()
            card.setObjectName("card")
            body = QVBoxLayout(card)
            body.setContentsMargins(12, 8, 12, 8)
            title = QLabel(label)
            title.setObjectName("cardTitle")
            body.addWidget(title)
            if group:
                for event in group:
                    body.addWidget(
                        QLabel(
                            f"  {fmt.clock(event.get('start_time'))}"
                            f"  {event['description']}"
                        )
                    )
            else:
                nothing = QLabel("  — nothing here")
                nothing.setObjectName("cardWhy")
                body.addWidget(nothing)
            self.cards.append(card)  # type: ignore[arg-type]
            self.cards_layout.insertWidget(
                self.cards_layout.count() - 1, card
            )
        self.empty_label.hide()
        self.summary_label.setText(
            f"Today so far: {len(completed)} done, {len(overdue)} overdue,"
            f" {len(upcoming)} still to come."
        )
