"""System tray: the product's face when every window is closed.

A painted status dot (no asset files to lose), a tooltip that names
each child's state, and the runtime menu. The tray never touches the
supervisor directly — it drives a small controller object the app
provides, so tests exercise the full menu against a fake.
"""

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QBrush, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QMessageBox, QSystemTrayIcon

#: Aggregate supervisor state -> dot colour.
STATE_COLORS = {
    "ok": "#2ecc71",
    "paused": "#f1c40f",
    "degraded": "#e74c3c",
    "stopped": "#7f8c8d",
}


def build_status_icon(state: str, size: int = 64) -> QIcon:
    """A filled dot in the state's colour on a transparent square."""
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor(STATE_COLORS.get(state, STATE_COLORS["stopped"]))
    painter.setBrush(QBrush(color))
    painter.setPen(QColor(30, 30, 30))
    margin = size // 8
    painter.drawEllipse(
        margin, margin, size - 2 * margin, size - 2 * margin
    )
    painter.end()
    return QIcon(pixmap)


def status_tooltip(overall: str, status: dict) -> str:
    parts = ", ".join(
        f"{name} {snapshot['state']}" for name, snapshot in status.items()
    )
    return f"PAIOS — {overall}" + (f" ({parts})" if parts else "")


class LauncherTray(QSystemTrayIcon):
    """Tray icon + menu wired to a controller.

    The controller must provide: ``open_dashboard()``,
    ``pause_runtime()``, ``resume_runtime()``, ``restart_runtime()``,
    ``view_logs()``, ``quit()``, ``overall_state() -> str`` and
    ``status() -> dict``.
    """

    REFRESH_MS = 1000

    def __init__(self, controller, parent=None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._menu = QMenu()
        self._status_action = QAction("Status: starting…", self._menu)
        self._status_action.setEnabled(False)
        self._menu.addAction(self._status_action)
        self._menu.addSeparator()
        self._actions = {}
        for key, label, slot in (
            ("open", "Open Dashboard", controller.open_dashboard),
            ("pause", "Pause Runtime", controller.pause_runtime),
            ("resume", "Resume Runtime", controller.resume_runtime),
            ("restart", "Restart Runtime", controller.restart_runtime),
            ("logs", "View Logs", controller.view_logs),
        ):
            action = QAction(label, self._menu)
            action.triggered.connect(slot)
            self._menu.addAction(action)
            self._actions[key] = action
        self._menu.addSeparator()
        # M20: update actions. "Install update" stays hidden until a
        # check finds one; installing hands over to PAIOSUpdater.exe.
        check_updates = QAction("Check for Updates", self._menu)
        check_updates.triggered.connect(controller.check_for_updates)
        self._menu.addAction(check_updates)
        self._actions["check_updates"] = check_updates
        install_update = QAction("Install Update", self._menu)
        install_update.triggered.connect(self.show_update_dialog)
        install_update.setVisible(False)
        self._menu.addAction(install_update)
        self._actions["install_update"] = install_update
        self._pending_update = None
        # Clicking the toast opens the same consent dialog.
        self.messageClicked.connect(self._on_message_clicked)
        self._menu.addSeparator()
        exit_action = QAction("Exit", self._menu)
        exit_action.triggered.connect(controller.quit)
        self._menu.addAction(exit_action)
        self._actions["exit"] = exit_action
        self.setContextMenu(self._menu)

        self._timer = QTimer(self)
        self._timer.setInterval(self.REFRESH_MS)
        self._timer.timeout.connect(self.refresh)
        self.refresh()

    # --- behaviour ---------------------------------------------------------

    def start_monitoring(self) -> None:
        self._timer.start()

    def stop_monitoring(self) -> None:
        self._timer.stop()

    def action(self, key: str) -> QAction:
        return self._actions[key]

    def refresh(self) -> None:
        overall = self._controller.overall_state()
        status = self._controller.status()
        self.setIcon(build_status_icon(overall))
        self.setToolTip(status_tooltip(overall, status))
        self._status_action.setText(f"Status: {overall}")
        daemon_state = status.get("daemon", {}).get("state")
        self._actions["pause"].setEnabled(daemon_state == "running")
        self._actions["resume"].setEnabled(
            daemon_state in ("paused", "stopped", "failed")
        )

    # --- updates (M20) -------------------------------------------------------

    def notify_update_available(self, update) -> None:
        """Surface a found update: menu entry + toast. Never installs,
        never interrupts — the user opens the consent dialog when ready."""
        self._pending_update = update
        action = self._actions["install_update"]
        action.setText(f"Install Update ({update.target})")
        action.setVisible(True)
        self.showMessage(
            f"PAIOS {update.target} available",
            f"You are on {update.current}. Click for what's new and to "
            "update — or keep working; nothing is interrupted.",
            QSystemTrayIcon.MessageIcon.Information,
            10_000,
        )

    def _on_message_clicked(self) -> None:
        if self._pending_update is not None:
            self.show_update_dialog()

    def build_update_dialog(self) -> QMessageBox | None:
        """The consent dialog: what's new + Update Now / Later. Split
        from show_update_dialog so tests can inspect it offscreen."""
        update = self._pending_update
        if update is None:
            return None
        dialog = QMessageBox()
        dialog.setWindowTitle("PAIOS Update")
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setText(
            f"PAIOS {update.target} is available (you are on "
            f"{update.current})."
        )
        notes = (update.notes or "").strip()
        dialog.setInformativeText(
            "PAIOS will close, update and restart automatically. "
            "A backup is kept and restored if anything goes wrong."
        )
        if notes:
            dialog.setDetailedText(notes)  # collapsible "What's new"
        update_now = dialog.addButton(
            "Update Now", QMessageBox.ButtonRole.AcceptRole
        )
        dialog.addButton("Later", QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(update_now)
        return dialog

    def show_update_dialog(self) -> None:
        dialog = self.build_update_dialog()
        if dialog is None:
            return
        dialog.exec()
        clicked = dialog.clickedButton()
        if clicked is not None and clicked.text() == "Update Now":
            self._controller.install_update()
