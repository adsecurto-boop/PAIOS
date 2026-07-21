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
from paios_gui.notifications import (
    DashboardWatcher,
    GuiNotification,
    NotificationCenter,
)
from paios_gui.pages import (
    EventsPage,
    GoalsPage,
    HistoryPage,
    KnowledgePage,
    LearningPage,
    NotificationsPage,
    ProjectsPage,
    ResourcesPage,
    SettingsPage,
)


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
        self._page_list: list[tuple[str, QWidget]] = [
            ("Dashboard", self.dashboard),
            ("Goals", GoalsPage(self)),
            ("Projects", ProjectsPage(self)),
            ("Events", EventsPage(self)),
            ("Resources", ResourcesPage(self)),
            ("Knowledge", KnowledgePage(self)),
            ("Learning", LearningPage(self)),
            ("History", HistoryPage(self)),
            ("Notifications", NotificationsPage(self)),
            ("Settings", SettingsPage(self)),
        ]
        self._notifications_row = 8  # nav index of the Notifications page
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

    def current_page(self) -> QWidget:
        return self._page_list[self.pages.currentIndex()][1]

    def _install_shortcuts(self) -> None:
        for keys in ("F5", "Ctrl+R"):
            QShortcut(QKeySequence(keys), self, activated=self.refresh_now)
        for index in range(min(9, len(self._page_list))):
            QShortcut(
                QKeySequence(f"Ctrl+{index + 1}"),
                self,
                activated=lambda row=index: self.navigation.setCurrentRow(row),
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
        """Perform one REST action; report the outcome; refresh the view."""
        try:
            call()
        except ApiUnreachable as error:
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
            "  ·  F5 refresh · Ctrl+1…9 pages · Ctrl+Q quit"
        )
