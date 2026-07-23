"""Navigation pages: read-only tables over list endpoints, plus the
page-local actions the mission requires. Each page's ``refresh(client)``
issues its GET calls; each toolbar button issues exactly one REST call
through the window's ``run_action``."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from paios_gui import format as fmt
from paios_gui.config import MAX_REFRESH_SECONDS, MIN_REFRESH_SECONDS
from paios_gui.dialogs import (
    NameDescriptionDialog,
    ProgressDialog,
    confirm,
)

#: Event states shown on the History page (terminal states — the same
#: canonical state names the TUI groups by).
_HISTORY_STATES = ("Completed", "Cancelled", "Archived", "Rejected", "Expired")


class TablePage(QWidget):
    """A titled table + toolbar; subclasses define columns and rows.

    Two shared presentation aids (M20): an empty-state hint shown when
    the fetch returns no rows, and a substring filter (the window's
    toolbar search) that hides non-matching rows — display only, the
    fetched data is untouched."""

    title = ""
    columns: tuple[str, ...] = ()
    empty_hint = "Nothing here yet."

    def __init__(self, window) -> None:
        super().__init__()
        self._window = window
        self._rows: list[dict] = []
        self._filter = ""
        layout = QVBoxLayout(self)
        heading = QLabel(self.title.upper())
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        self.toolbar = QHBoxLayout()
        layout.addLayout(self.toolbar)
        self.empty_label = QLabel(self.empty_hint)
        self.empty_label.setWordWrap(True)
        self.empty_label.hide()
        layout.addWidget(self.empty_label)
        self.table = QTableWidget(0, len(self.columns))
        self.table.setHorizontalHeaderLabels(list(self.columns))
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)
        self._build_toolbar()
        self.toolbar.addStretch(1)

    def _build_toolbar(self) -> None:
        """Subclasses add their action buttons here."""

    def _add_button(self, label: str, handler) -> QPushButton:
        button = QPushButton(label)
        button.clicked.connect(handler)
        self.toolbar.addWidget(button)
        return button

    # --- data ------------------------------------------------------------

    def refresh(self, client) -> None:
        self._rows = self.fetch(client)
        self.table.setRowCount(len(self._rows))
        for row_index, row in enumerate(self._rows):
            for column_index, value in enumerate(self.cells(row)):
                item = QTableWidgetItem(value)
                item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )
                self.table.setItem(row_index, column_index, item)
        self.empty_label.setVisible(not self._rows)
        self._apply_row_filter()

    # --- search filter (presentation only) --------------------------------

    def apply_filter(self, text: str) -> None:
        self._filter = text.strip().lower()
        self._apply_row_filter()

    def _apply_row_filter(self) -> None:
        for row_index, row in enumerate(self._rows):
            matches = not self._filter or any(
                self._filter in value.lower() for value in self.cells(row)
            )
            self.table.setRowHidden(row_index, not matches)

    def fetch(self, client) -> list[dict]:
        raise NotImplementedError

    def cells(self, row: dict) -> tuple[str, ...]:
        raise NotImplementedError

    def selected_row(self) -> dict | None:
        index = self.table.currentRow()
        if 0 <= index < len(self._rows):
            return self._rows[index]
        return None

    def _require_selection(self) -> dict | None:
        row = self.selected_row()
        if row is None:
            self._window.notify("Select a row first.", "warn")
        return row


class GoalsPage(TablePage):
    title = "Goals"
    columns = ("Name", "Status", "Suggested by", "Accepted", "Description")

    def _build_toolbar(self) -> None:
        self._add_button("New goal…", self._on_new)

    def fetch(self, client):
        return client.get_goals()

    def cells(self, row):
        return (
            row["name"],
            row["status"],
            row["suggested_by"],
            fmt.day_time(row["accepted_at"]),
            row["description"],
        )

    def _on_new(self) -> None:
        dialog = NameDescriptionDialog("New goal", self)
        if dialog.exec():
            values = dialog.values()
            self._window.run_action(
                lambda: self._window.client.create_goal(
                    values["name"], values["description"]
                ),
                f"Goal created: {values['name']}",
            )


class ProjectsPage(TablePage):
    title = "Projects"
    columns = ("Name", "Status", "Progress", "Velocity", "Created")

    def _build_toolbar(self) -> None:
        self._add_button("New project…", self._on_new)
        self._add_button("Update progress…", self._on_progress)

    def fetch(self, client):
        return client.get_projects()

    def cells(self, row):
        progress = row.get("progress") or {}
        return (
            row["name"],
            row["status"],
            fmt.percent(progress.get("completion_percentage")),
            fmt.text_or_dash(progress.get("velocity")),
            fmt.day_time(row["created_at"]),
        )

    def _on_new(self) -> None:
        dialog = NameDescriptionDialog("New project", self)
        if dialog.exec():
            values = dialog.values()
            self._window.run_action(
                lambda: self._window.client.create_project(
                    values["name"], values["description"]
                ),
                f"Project created: {values['name']}",
            )

    def _on_progress(self) -> None:
        row = self._require_selection()
        if row is None:
            return
        current = (row.get("progress") or {}).get("completion_percentage", 0.0)
        dialog = ProgressDialog(row["name"], current or 0.0, self)
        if dialog.exec():
            percentage = dialog.values()["completion_percentage"]
            self._window.run_action(
                lambda: self._window.client.update_progress(
                    row["project_id"], percentage
                ),
                f"Progress updated: {row['name']} -> {percentage:.0f}%",
            )


class ResourcesPage(TablePage):
    title = "Resources"
    columns = ("Type", "Value", "Unit", "Negative allowed", "Updated")

    def fetch(self, client):
        return client.get_resources()

    def cells(self, row):
        return (
            row["type"],
            f"{row['current_value']:g}",
            row["unit"],
            "yes" if row["negative_allowed"] else "no",
            fmt.day_time(row["last_updated"]),
        )


class KnowledgePage(TablePage):
    title = "Knowledge"
    columns = (
        "Domain", "Topic", "Concept", "Confidence", "Revisions", "Last revision"
    )

    def fetch(self, client):
        return client.get_knowledge()

    def cells(self, row):
        return (
            row["domain"],
            row["topic"],
            row["concept"],
            f"{row['confidence']:.2f}",
            str(row["revision_count"]),
            fmt.day_time(row["last_revision"]),
        )


class LearningPage(TablePage):
    """Reflections table + the learning summary from /dashboard."""

    title = "Learning"
    columns = ("Created", "Lesson learned", "Improvement", "Confidence")

    def __init__(self, window) -> None:
        super().__init__(window)
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.layout().insertWidget(1, self.summary)

    def fetch(self, client):
        learning = client.get_dashboard()["learning"]
        insight = learning.get("latest_insight")
        self.summary.setText(
            f"Last studied: {fmt.day_time(learning['last_studied'])}"
            f"   ·   Revised today: {learning['revised_today']}"
            f"   ·   Latest insight: "
            + (
                f"[{insight['category']}] confidence {insight['confidence']:.2f}"
                if insight
                else "none"
            )
        )
        return client.get_reflections()[::-1]

    def cells(self, row):
        return (
            fmt.day_time(row["created_at"]),
            fmt.text_or_dash(row["lesson_learned"]),
            fmt.text_or_dash(row["improvement"]),
            fmt.text_or_dash(row["confidence"]),
        )


class HistoryPage(TablePage):
    """Terminal-state events with their full transition history."""

    title = "History"
    columns = ("Description", "Status", "Ended", "Outcome", "Transitions")

    def fetch(self, client):
        return [
            event
            for event in client.get_events()
            if event["status"] in _HISTORY_STATES
        ]

    def cells(self, row):
        transitions = " > ".join(
            f"{record['to_state']} {fmt.clock(record['occurred_at'])}"
            for record in row["transitions"]
        )
        return (
            row["description"],
            row["status"],
            fmt.day_time(row["end_time"]),
            fmt.text_or_dash(row["outcome"]),
            transitions,
        )


class NotificationsPage(TablePage):
    """The notification center (M14): history list, unread state, and
    the two maintenance actions. Reads the window's NotificationCenter —
    notifications are GUI presentation state, not a REST resource."""

    title = "Notifications"
    columns = ("", "Time", "Category", "Message")

    def _build_toolbar(self) -> None:
        self._add_button("Mark all read", self._on_mark_read)
        self._add_button("Clear", self._on_clear)

    def fetch(self, client):
        return self._window.notification_center.entries()

    def cells(self, row):
        return (
            "" if row.read else "*",
            row.occurred_at or "—",
            row.category,
            row.message,
        )

    def _on_mark_read(self) -> None:
        self._window.notification_center.mark_all_read()
        self._window.refresh_now()

    def _on_clear(self) -> None:
        self._window.notification_center.clear()
        self._window.refresh_now()



class BackupsPage(TablePage):
    """Backup manager (M20): list archives, create one, restore one.
    Restore only unpacks files — the server adopts them at its next
    start, which the confirm dialog spells out."""

    title = "Backups"
    columns = ("Archive", "Size")
    empty_hint = "No backups yet. Create one with the button above."

    def _build_toolbar(self) -> None:
        self._add_button("Create backup", self._on_create)
        self._add_button("Restore…", self._on_restore)

    def fetch(self, client):
        return client.list_backups()

    def cells(self, row):
        return (row["name"], f"{row['size_bytes']:,} bytes")

    def _on_create(self) -> None:
        self._window.run_action(
            lambda: self._window.client.create_backup(),
            "Backup created",
        )

    def _on_restore(self) -> None:
        row = self._require_selection()
        if row is None:
            return
        if not confirm(
            self,
            "Restore backup",
            f"Restore '{row['name']}'? Restored files load at the next"
            " application start — restart PAIOS afterwards to adopt them.",
        ):
            return
        self._window.run_action(
            lambda: self._window.client.restore_backup(row["name"]),
            f"Backup restored: {row['name']} (restart PAIOS to adopt)",
        )


class MobileDevicesPage(TablePage):
    """Phone pairing without a terminal: generate the 6-digit code,
    see trusted devices, revoke one. Every button is one REST call."""

    title = "Mobile"
    columns = ("Device", "Paired", "Last seen")
    empty_hint = (
        "No phone paired yet. Click 'Generate pairing code', install"
        " the PAIOS companion app on your phone, and enter the code in"
        " its Settings → Pair with desktop."
    )

    #: The pairing code lives for five minutes (mobile_support TTL); the
    #: countdown is local so it is right whatever clock the server uses.
    CODE_TTL_SECONDS = 5 * 60

    def __init__(self, window) -> None:
        super().__init__(window)
        # The code panel sits between the toolbar and the table.
        self.code_label = QLabel("")
        self.code_label.setObjectName("todayHeader")
        self.code_label.hide()
        self.countdown_label = QLabel("")
        self.countdown_label.setObjectName("statusChip")
        self.countdown_label.hide()
        self.code_hint = QLabel("")
        self.code_hint.setObjectName("subtitle")
        self.code_hint.setWordWrap(True)
        self.code_hint.hide()
        self.qr_label = QLabel("")
        self.qr_label.hide()
        layout = self.layout()
        layout.insertWidget(2, self.code_label)
        layout.insertWidget(3, self.countdown_label)
        layout.insertWidget(4, self.qr_label)
        layout.insertWidget(5, self.code_hint)
        # One-second expiry countdown for the visible code.
        self._remaining = 0
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick_countdown)

    def _build_toolbar(self) -> None:
        self._add_button("Generate pairing code", self.on_generate)
        self._add_button("Revoke device", self.on_revoke)

    def fetch(self, client) -> list[dict]:
        return client.mobile_devices()

    def cells(self, row: dict) -> tuple[str, ...]:
        return (
            row.get("name") or "(unnamed device)",
            fmt.day_time(row.get("paired_at")),
            fmt.day_time(row.get("last_seen")),
        )

    def on_generate(self) -> None:
        def call() -> None:
            payload = self._window.client.mobile_pairing_start()
            code = payload.get("code", "")
            self.code_label.setText(f"Pairing code:  {code}")
            self.code_label.show()
            self._start_countdown()
            address, on_lan, remote_on = self._connection_info()
            self._show_qr(address, remote_on)
            steps = (
                "1. On the phone app: Settings → Pair with desktop.\n"
                f"2. Enter the server address: {address}\n"
                "3. Type the code above (or scan the QR). The code works"
                " once, within 5 minutes."
            )
            if remote_on:
                steps += (
                    "\n\nRemote access is on — after pairing, the phone"
                    " works from any network, not just this Wi-Fi."
                )
            elif not on_lan:
                steps += (
                    "\n\nNote: PAIOS is in Local Only mode, so the phone"
                    " cannot reach it yet. Turn on Local Network (or set"
                    " up Remote access) on the Networking page first."
                )
            self.code_hint.setText(steps)
            self.code_hint.show()

        self._window.run_action(call, "Pairing code generated")

    def _connection_info(self) -> tuple[str, bool, bool]:
        """(human address, is-LAN-reachable, is-remote-on). Falls back
        to the client's base URL if networking is unavailable."""
        try:
            facts = self._window.client.system_network()
        except Exception:
            return self._window.client.base_url, False, False
        on_lan = facts.get("mode") == "lan"
        address = facts.get("lan_url") if on_lan else facts.get(
            "loopback_url"
        )
        remote_on = False
        try:
            relay = self._window.client.system_relay()
            remote_on = bool(relay.get("enabled") and relay.get("relay_url"))
            self._relay = relay
        except Exception:
            self._relay = {}
        return address or self._window.client.base_url, on_lan, remote_on

    def _show_qr(self, address: str, remote_on: bool) -> None:
        from paios_gui import qr

        relay = getattr(self, "_relay", {}) or {}
        payload = qr.connection_uri(
            lan_url=address if not address.startswith("http://127.") else None,
            relay_url=relay.get("relay_url") if remote_on else None,
            account=relay.get("account", "default"),
        ) or address
        self.qr_label.setPixmap(qr.pixmap(payload))
        self.qr_label.show()

    def _start_countdown(self) -> None:
        self._remaining = self.CODE_TTL_SECONDS
        self._render_countdown()
        self.countdown_label.show()
        self._timer.start()

    def _tick_countdown(self) -> None:
        self._remaining -= 1
        if self._remaining <= 0:
            self._timer.stop()
            self.countdown_label.setText("Code expired — generate a new one")
            self.code_label.hide()
            self.qr_label.hide()
            return
        self._render_countdown()

    def _render_countdown(self) -> None:
        minutes, seconds = divmod(max(self._remaining, 0), 60)
        self.countdown_label.setText(f"Expires in {minutes}:{seconds:02d}")

    def on_revoke(self) -> None:
        row = self._require_selection()
        if row is None:
            return
        name = row.get("name") or row.get("device_id", "device")
        if not confirm(
            self,
            "Revoke device",
            f"Revoke '{name}'? The phone will need to pair again.",
        ):
            return
        self._window.run_action(
            lambda: self._window.client.mobile_revoke_device(
                row["device_id"]
            ),
            f"Device revoked: {name}",
        )


class SettingsPage(QWidget):
    """Refresh interval (the configurable poll) and connection info."""

    title = "Settings"

    def __init__(self, window) -> None:
        super().__init__()
        self._window = window
        layout = QVBoxLayout(self)
        heading = QLabel("SETTINGS")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)

        row = QHBoxLayout()
        interval_label = QLabel("Refresh interval (seconds):")
        row.addWidget(interval_label)
        self.interval = QSpinBox()
        self.interval.setRange(MIN_REFRESH_SECONDS, MAX_REFRESH_SECONDS)
        self.interval.setValue(window.config.refresh_seconds)
        self.interval.setAccessibleName("Refresh interval in seconds")
        self.interval.valueChanged.connect(window.set_refresh_interval)
        row.addWidget(self.interval)
        row.addStretch(1)
        layout.addLayout(row)

        # Theme switch (M24): dark or light, applied live and persisted.
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Theme:"))
        self.theme_box = QComboBox()
        self.theme_box.addItems(["dark", "light"])
        self.theme_box.setCurrentText(getattr(window.config, "theme", "dark"))
        self.theme_box.setAccessibleName("Application theme")
        self.theme_box.currentTextChanged.connect(window.set_theme)
        theme_row.addWidget(self.theme_box)
        theme_row.addStretch(1)
        layout.addLayout(theme_row)

        self.server_label = QLabel(f"Server: {window.client.base_url}")
        layout.addWidget(self.server_label)
        shortcuts_button = QPushButton("Keyboard shortcuts (F1)…")
        shortcuts_button.clicked.connect(window.show_shortcuts)
        layout.addWidget(shortcuts_button)
        layout.addStretch(1)

    def refresh(self, client) -> None:
        """Settings shows configuration, not server data."""
