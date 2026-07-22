"""The main window: navigation, polling, actions, error handling.

Every byte shown comes from REST responses; every button press performs
exactly one REST call. Failures never crash the window:

- ApiUnreachable  -> red OFFLINE banner, notice logged once per outage,
  and the poll timer keeps retrying (graceful retry).
- ApiResponseError -> the API's own error message in the status bar and
  the notification log (validation failures surface verbatim).
"""

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from paios_gui import format as fmt
from paios_gui.client import ApiClient, ApiResponseError, ApiUnreachable
from paios_gui.config import GuiConfig
from paios_gui.dashboard_page import DashboardPage
from paios_gui.events_page import EventsPage
from paios_gui.inbox_page import InboxPage
from paios_gui.log_page import LogPage
from paios_gui.notifications import (
    DashboardWatcher,
    GuiNotification,
    NotificationCenter,
)
from paios_gui.pages import (
    BackupsPage,
    GoalsPage,
    HistoryPage,
    KnowledgePage,
    LearningPage,
    NotificationsPage,
    ProjectsPage,
    ResourcesPage,
    SettingsPage,
)
from paios_gui.planning_page import PlanningPage
from paios_gui.timeline_page import TimelinePage


class MainWindow(QMainWindow):
    def __init__(self, client: ApiClient, config: GuiConfig) -> None:
        super().__init__()
        self.client = client
        self.config = config
        self.online: bool | None = None  # unknown until the first poll
        self._last_refresh: str | None = None
        # M14: notification center + the poll-diff watcher feeding it.
        self.notification_center = NotificationCenter()
        self._watcher = DashboardWatcher()
        self._tray = self._create_tray()

        self.setWindowTitle("PAIOS — Desktop Dashboard")
        self.resize(1100, 760)

        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(8, 8, 8, 8)

        self.banner = QLabel("")
        self.banner.setObjectName("banner")
        self.banner.hide()
        outer.addWidget(self.banner)

        # M20 toolbar search: a substring filter over the current
        # table page's rows — presentation only, data untouched.
        search_row = QHBoxLayout()
        search_row.addStretch(1)
        search_row.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("filter current table (Ctrl+F)")
        self.search_edit.setFixedWidth(260)
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search)
        search_row.addWidget(self.search_edit)
        outer.addLayout(search_row)

        body = QHBoxLayout()
        outer.addLayout(body, stretch=1)

        self.navigation = QListWidget()
        self.navigation.setObjectName("navigation")
        self.navigation.setFixedWidth(150)
        body.addWidget(self.navigation)

        self.pages = QStackedWidget()
        body.addWidget(self.pages, stretch=1)
        self.setCentralWidget(central)

        self.dashboard = DashboardPage(self)
        self.planning = PlanningPage(self)
        self.inbox = InboxPage(self)
        self.events_page = EventsPage(self)
        # M20 nav order: Planning first — it is the startup page.
        self._page_list: list[tuple[str, QWidget]] = [
            ("Planning", self.planning),
            ("Timeline", TimelinePage(self)),
            ("Inbox", self.inbox),
            ("Dashboard", self.dashboard),
            ("Goals", GoalsPage(self)),
            ("Projects", ProjectsPage(self)),
            ("Events", self.events_page),
            ("Resources", ResourcesPage(self)),
            ("Knowledge", KnowledgePage(self)),
            ("Learning", LearningPage(self)),
            ("History", HistoryPage(self)),
            ("Backups", BackupsPage(self)),
            ("Logs", LogPage(self)),
            ("Notifications", NotificationsPage(self)),
            ("Settings", SettingsPage(self)),
        ]
        #: Nav index of the Notifications page (looked up, not counted).
        self._notifications_row = [
            name for name, _ in self._page_list
        ].index("Notifications")
        for name, page in self._page_list:
            self.navigation.addItem(name)
            self.pages.addWidget(page)
        self.navigation.addItem("Refresh")  # nav-accessible manual refresh
        self.navigation.currentRowChanged.connect(self._on_navigate)
        self.navigation.setCurrentRow(0)

        self.statusBar().showMessage("Ready")
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh_now)
        self._timer.start(self.config.refresh_seconds * 1000)
        self._install_shortcuts()

    # --- navigation ------------------------------------------------------

    def _on_navigate(self, row: int) -> None:
        if row == len(self._page_list):  # the trailing "Refresh" entry
            self.navigation.setCurrentRow(self.pages.currentIndex())
            self.refresh_now()
            return
        if 0 <= row < len(self._page_list):
            self.pages.setCurrentIndex(row)
            self.refresh_now()
            self._on_search(self.search_edit.text())

    def current_page(self) -> QWidget:
        return self._page_list[self.pages.currentIndex()][1]

    def _row_of(self, name: str) -> int:
        return [page_name for page_name, _ in self._page_list].index(name)

    def _on_search(self, text: str) -> None:
        page = self.current_page()
        if hasattr(page, "apply_filter"):
            page.apply_filter(text)

    def _on_new_event(self) -> None:
        """Ctrl+N: jump to Events and open the New Event dialog."""
        self.navigation.setCurrentRow(self._row_of("Events"))
        self.events_page.on_new()

    def _on_focus_inbox(self) -> None:
        """Ctrl+I: jump to Inbox and focus the capture box."""
        self.navigation.setCurrentRow(self._row_of("Inbox"))
        self.inbox.focus_capture()

    def _install_shortcuts(self) -> None:
        for keys in ("F5", "Ctrl+R"):
            QShortcut(QKeySequence(keys), self, activated=self.refresh_now)
        for index in range(min(9, len(self._page_list))):
            QShortcut(
                QKeySequence(f"Ctrl+{index + 1}"),
                self,
                activated=lambda row=index: self.navigation.setCurrentRow(row),
            )
        QShortcut(
            QKeySequence("Ctrl+N"), self, activated=self._on_new_event
        )
        QShortcut(
            QKeySequence("Ctrl+I"), self, activated=self._on_focus_inbox
        )
        QShortcut(
            QKeySequence("Ctrl+P"),
            self,
            activated=lambda: self.navigation.setCurrentRow(
                self._row_of("Planning")
            ),
        )
        QShortcut(
            QKeySequence("Ctrl+F"),
            self,
            activated=lambda: self.search_edit.setFocus(),
        )
        quit_action = QAction(self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        self.addAction(quit_action)

    # --- polling ---------------------------------------------------------

    def refresh_now(self) -> None:
        """Fetch what the visible page needs. Never raises.

        `/dashboard` is fetched on every poll regardless of page — it
        feeds the notification watcher, so news is noticed while any
        page is open."""
        page = self.current_page()
        try:
            dashboard = self.client.get_dashboard()
            if page is self.dashboard:
                resources = self.client.get_resources()
                reflections = self.client.get_reflections()
                self.dashboard.update_data(dashboard, resources, reflections)
            else:
                page.refresh(self.client)
            self._last_refresh = fmt.clock(dashboard["current_time"])
        except ApiUnreachable as error:
            self._set_online(False, str(error))
            return
        except ApiResponseError as error:
            # The server is up but refused a read (e.g. restarting): show
            # the message, keep the last rendered data, keep polling.
            self.notify(f"Server error: {error}", "error")
            return
        self._set_online(True)
        self._absorb(self._watcher.observe(dashboard))
        self._update_notifications_view()
        self._update_footer()

    def set_refresh_interval(self, seconds: int) -> None:
        self.config.refresh_seconds = self.config.clamp_refresh(int(seconds))
        self._timer.start(self.config.refresh_seconds * 1000)
        self._update_footer()

    # --- actions ---------------------------------------------------------

    def run_action(self, call, success_notice: str) -> None:
        """Perform one REST action; report the outcome; refresh the view.
        A busy note shows while the (synchronous) request runs."""
        self.statusBar().showMessage("Working…")
        try:
            call()
        except ApiUnreachable as error:
            self.statusBar().showMessage("Offline — action not sent", 8000)
            self._set_online(False, str(error))
            return
        except ApiResponseError as error:
            self.notify(f"Rejected: {error} ({error.error_type})", "error")
            return
        self.notify(success_notice, "ok")
        self.refresh_now()

    def notify(self, text: str, kind: str = "info") -> None:
        """Action feedback and connection changes: status bar + feed +
        center history (no desktop toast — the user is looking already)."""
        import logging

        logging.getLogger("paios.gui").info("kind=%s message=%s", kind, text)
        self.statusBar().showMessage(text, 8000)
        self.dashboard.notice_log.add_notice(text, kind)
        self.notification_center.add(
            GuiNotification(message=text, category="App", kind=kind)
        )
        self._update_notifications_view()

    # --- notification center (M14) ---------------------------------------

    def _absorb(self, fresh: list[GuiNotification]) -> None:
        """Record watcher findings; toast them — they happened elsewhere."""
        for notification in fresh:
            self.notification_center.add(notification)
            self.dashboard.notice_log.add_notice(
                notification.message, notification.kind
            )
            self._toast(notification)
        if fresh:
            self._update_notifications_view()

    def _toast(self, notification: GuiNotification) -> None:
        if self._tray is None:
            return
        from PySide6.QtWidgets import QSystemTrayIcon

        self._tray.showMessage(
            "PAIOS",
            notification.message,
            (
                QSystemTrayIcon.MessageIcon.Critical
                if notification.kind == "error"
                else QSystemTrayIcon.MessageIcon.Information
            ),
            6000,
        )

    def _create_tray(self):
        """A tray icon for desktop toasts; None where no tray exists
        (headless test runs, some desktops) — the center still records."""
        from PySide6.QtWidgets import QApplication, QStyle, QSystemTrayIcon

        try:
            if not QSystemTrayIcon.isSystemTrayAvailable():
                return None
            icon = QApplication.instance().style().standardIcon(
                QStyle.StandardPixmap.SP_MessageBoxInformation
            )
            tray = QSystemTrayIcon(icon, self)
            tray.setToolTip("PAIOS")
            tray.show()
            return tray
        except Exception:
            return None

    def _update_notifications_view(self) -> None:
        """Badge on the nav entry + live table when the page is visible."""
        unread = self.notification_center.unread_count
        item = self.navigation.item(self._notifications_row)
        item.setText(
            f"Notifications ({unread})" if unread else "Notifications"
        )
        page = self._page_list[self._notifications_row][1]
        if self.pages.currentWidget() is page:
            page.refresh(self.client)

    # --- connection state ------------------------------------------------

    def _set_online(self, online: bool, detail: str = "") -> None:
        changed = online is not self.online
        self.online = online
        if online:
            self.banner.hide()
            if changed:
                self.notify("Connected to PAIOS.", "ok")
        else:
            self.banner.setText(
                "OFFLINE — server unreachable, retrying every "
                f"{self.config.refresh_seconds}s"
            )
            self.banner.show()
            if changed:
                self.notify(f"Connection lost: {detail}", "error")
        self._update_footer()

    def _update_footer(self) -> None:
        state = {True: "online", False: "OFFLINE", None: "connecting"}[
            self.online
        ]
        self.dashboard.set_footer(
            f"{self.client.base_url}  ·  {state}"
            f"  ·  refresh every {self.config.refresh_seconds}s"
            f"  ·  last data: {self._last_refresh or '—'}"
            "  ·  F5 refresh · Ctrl+1…9 pages · Ctrl+N new event"
            " · Ctrl+F search · Ctrl+Q quit"
        )
