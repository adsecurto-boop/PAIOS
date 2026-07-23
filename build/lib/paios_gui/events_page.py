"""The Events page (M20): a day-grouped card board, not a table.

Closer to a calendar than an admin grid: events group under date
headers (soonest day first, unscheduled last), each as a card with a
colored status chip, its primary lifecycle button(s) for the current
state, and a "⋯" menu holding the rest (edit, duplicate, template,
cancel, archive — archive is the only removal; no hard delete exists).
Every button performs exactly one REST call through the window's
``run_action``; state decisions stay on the server — the card merely
mirrors ``status``.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from paios_gui import format as fmt
from paios_gui import theme
from paios_gui.dialogs import (
    DuplicateDialog,
    EventDialog,
    OutcomeDialog,
    ReasonDialog,
    RecurrencesDialog,
    ReflectionDialog,
    SaveTemplateDialog,
    TemplatesDialog,
    confirm,
)

#: The metadata fields the sidecar carries; used to copy a clean
#: metadata block out of a fetched record (which also holds keys like
#: "key"/"updated_at" that must not travel back).
METADATA_FIELDS = (
    "tags", "deadline", "energy", "estimated_duration_minutes", "depends_on",
)


class EventsPage(QWidget):
    title = "Events"

    def __init__(self, window) -> None:
        super().__init__()
        self._window = window
        self._rows: list[dict] = []
        self._filter = ""
        self._groups: list[tuple[QLabel, list[tuple[QFrame, str]]]] = []
        layout = QVBoxLayout(self)
        heading = QLabel("EVENTS")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)

        toolbar = QHBoxLayout()
        for label, handler in (
            ("New event…", self.on_new),
            ("Templates…", self._on_templates),
            ("Recurrences…", self._on_recurrences),
        ):
            button = QPushButton(label)
            button.clicked.connect(handler)
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        self.empty_label = QLabel(
            "No events yet. Create one with New event… (Ctrl+N) or"
            " accept a recommendation from the Dashboard."
        )
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self._cards_layout = QVBoxLayout(container)
        self._cards_layout.addStretch(1)
        scroll.setWidget(container)
        layout.addWidget(scroll, stretch=1)

    # --- data ------------------------------------------------------------

    def refresh(self, client) -> None:
        self._rows = client.get_events()
        self._rebuild()

    def _rebuild(self) -> None:
        # Drop the old board (index [count-1] is the trailing stretch).
        while self._cards_layout.count() > 1:
            item = self._cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self._groups = []
        self.empty_label.setVisible(not self._rows)

        grouped: dict[str, list[dict]] = {}
        for event in self._rows:
            day = (event.get("start_time") or "")[:10] or "Unscheduled"
            grouped.setdefault(day, []).append(event)
        # Dated days soonest first; the undated bucket last.
        days = sorted(key for key in grouped if key != "Unscheduled")
        if "Unscheduled" in grouped:
            days.append("Unscheduled")
        position = 0
        for day in days:
            header = QLabel(day.upper())
            header.setObjectName("sectionTitle")
            self._cards_layout.insertWidget(position, header)
            position += 1
            cards: list[tuple[QFrame, str]] = []
            for event in sorted(
                grouped[day], key=lambda item: item.get("start_time") or ""
            ):
                card = self._build_card(event)
                searchable = " ".join(
                    (
                        event["description"],
                        event.get("category") or "",
                        event["status"],
                    )
                ).lower()
                cards.append((card, searchable))
                self._cards_layout.insertWidget(position, card)
                position += 1
            self._groups.append((header, cards))
        self._apply_card_filter()

    # --- search filter (presentation only) --------------------------------

    def apply_filter(self, text: str) -> None:
        self._filter = text.strip().lower()
        self._apply_card_filter()

    def _apply_card_filter(self) -> None:
        for header, cards in self._groups:
            any_visible = False
            for card, searchable in cards:
                visible = not self._filter or self._filter in searchable
                card.setVisible(visible)
                any_visible = any_visible or visible
            header.setVisible(any_visible)

    # --- card construction --------------------------------------------------

    def _build_card(self, event: dict) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        row = QHBoxLayout(card)
        row.setContentsMargins(12, 8, 12, 8)

        text_column = QVBoxLayout()
        title = QLabel(event["description"])
        title.setObjectName("cardTitle")
        title.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        text_column.addWidget(title)
        details = QLabel(
            f"{fmt.clock(event.get('start_time'))}"
            f" · {fmt.minutes(event.get('duration_minutes'))}"
            f" · {fmt.text_or_dash(event.get('category'))}"
        )
        details.setObjectName("subtitle")
        text_column.addWidget(details)
        row.addLayout(text_column, stretch=1)

        chip = QLabel(event["status"])
        chip.setObjectName("statusChip")
        color = theme.status_color(event["status"])
        chip.setStyleSheet(
            f"color: {theme.BACKGROUND}; background: {color};"
        )
        row.addWidget(chip)

        for label, handler in self._primary_actions(event):
            button = QPushButton(label)
            button.clicked.connect(handler)
            row.addWidget(button)
        more = QPushButton("⋯")
        more.setFixedWidth(36)
        more.setMenu(self._more_menu(event, more))
        row.addWidget(more)
        return card

    def _primary_actions(self, event: dict):
        """The state's obvious next step(s) — everything else is in ⋯."""
        status = event["status"]
        if status in ("Created", "Ready"):
            return ((
                "Start",
                lambda: self._simple(event, "start_event", "Event started"),
            ),)
        if status in ("Started", "Resumed"):
            return (
                (
                    "Pause",
                    lambda: self._simple(
                        event, "pause_event", "Event paused"
                    ),
                ),
                ("Complete…", lambda: self._on_complete(event)),
            )
        if status == "Paused":
            return (
                (
                    "Resume",
                    lambda: self._simple(
                        event, "resume_event", "Event resumed"
                    ),
                ),
                ("Complete…", lambda: self._on_complete(event)),
            )
        if status == "Completed":
            return (("Reflect…", lambda: self._on_reflect(event)),)
        return ()

    def _more_menu(self, event: dict, parent: QWidget) -> QMenu:
        menu = QMenu(parent)
        for label, handler in (
            ("Edit…", lambda: self._on_edit(event)),
            ("Duplicate…", lambda: self._on_duplicate(event)),
            ("Save as template…", lambda: self._on_save_template(event)),
            ("Cancel…", lambda: self._on_cancel(event)),
            ("Archive…", lambda: self._on_archive(event)),
        ):
            action = menu.addAction(label)
            action.triggered.connect(
                lambda _checked=False, call=handler: call()
            )
        return menu

    # --- lifecycle actions (one REST call each) -------------------------------

    def _simple(self, event: dict, method_name: str, notice: str) -> None:
        client_method = getattr(self._window.client, method_name)
        self._window.run_action(
            lambda: client_method(event["event_id"]), notice
        )

    def _on_complete(self, event: dict) -> None:
        dialog = OutcomeDialog(self)
        if dialog.exec():
            outcome = dialog.values()["actual_outcome"]
            self._window.run_action(
                lambda: self._window.client.complete_event(
                    event["event_id"], outcome
                ),
                "Event completed",
            )

    def _on_cancel(self, event: dict) -> None:
        dialog = ReasonDialog("Cancel event", "Reason (optional)", self)
        if dialog.exec():
            reason = dialog.values()["reason"]
            self._window.run_action(
                lambda: self._window.client.cancel_event(
                    event["event_id"], reason
                ),
                "Event cancelled",
            )

    def _on_reflect(self, event: dict) -> None:
        dialog = ReflectionDialog(event["description"], self)
        if dialog.exec():
            values = dialog.values()
            self._window.run_action(
                lambda: self._window.client.create_reflection(
                    event["event_id"], **values
                ),
                "Reflection recorded",
            )

    # --- authoring actions ----------------------------------------------------

    def on_new(self) -> None:
        """Public: also the window's Ctrl+N target."""
        dialog = EventDialog("New event", self)
        if dialog.exec():
            values = dialog.values()
            self._window.run_action(
                lambda: self._window.client.create_event(**values),
                f"Event proposed: {values['title']}",
            )

    def _on_edit(self, event: dict) -> None:
        try:
            metadata = self._window.client.get_event_metadata(
                event["event_id"]
            )
        except Exception:
            metadata = {}
        dialog = EventDialog(f"Edit — {event['description']}", self)
        dialog.prefill(event, metadata)
        if dialog.exec():
            values = dialog.values()
            title = values.pop("title")
            self._window.run_action(
                lambda: self._window.client.edit_event(
                    event["event_id"], title, **values
                ),
                f"Event edited (recreated): {title}",
            )

    def _on_duplicate(self, event: dict) -> None:
        dialog = DuplicateDialog(event["description"], self)
        if dialog.exec():
            when = dialog.values()["suggested_time"]
            self._window.run_action(
                lambda: self._window.client.duplicate_event(
                    event["event_id"], suggested_time=when
                ),
                f"Event duplicated: {event['description']}",
            )

    def _on_archive(self, event: dict) -> None:
        if not confirm(
            self,
            "Archive event",
            f"Archive '{event['description']}'? Archiving removes the"
            " event from active views (there is no hard delete).",
        ):
            return
        self._window.run_action(
            lambda: self._window.client.archive_event(event["event_id"]),
            f"Event archived: {event['description']}",
        )

    def _on_save_template(self, event: dict) -> None:
        dialog = SaveTemplateDialog(self)
        if dialog.exec():
            name = dialog.values()["name"]
            try:
                record = self._window.client.get_event_metadata(
                    event["event_id"]
                )
            except Exception:
                record = {}
            metadata = {
                field: record[field]
                for field in METADATA_FIELDS
                if field in record
            }
            self._window.run_action(
                lambda: self._window.client.create_template(
                    name,
                    event["description"],
                    category=event.get("category"),
                    metadata=metadata or None,
                ),
                f"Template saved: {name}",
            )

    def _on_templates(self) -> None:
        TemplatesDialog(self._window, self).exec()

    def _on_recurrences(self) -> None:
        RecurrencesDialog(self._window, self).exec()
