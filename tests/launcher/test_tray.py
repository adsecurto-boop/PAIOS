"""Tray behaviour against a fake controller (offscreen Qt)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from paios_launcher.tray import (
    LauncherTray,
    STATE_COLORS,
    build_status_icon,
    status_tooltip,
)


@pytest.fixture(scope="session")
def qapp():
    application = QApplication.instance() or QApplication([])
    yield application


class FakeController:
    def __init__(self):
        self.calls = []
        self._overall = "ok"
        self._status = {
            "daemon": {"state": "running", "pid": 111, "restarts": 0},
            "api": {"state": "running", "pid": 222, "restarts": 0},
            "gui": {"state": "stopped", "pid": None, "restarts": 0},
        }

    def set_state(self, overall, daemon_state):
        self._overall = overall
        self._status["daemon"]["state"] = daemon_state

    def overall_state(self):
        return self._overall

    def status(self):
        return self._status

    def open_dashboard(self):
        self.calls.append("open_dashboard")

    def pause_runtime(self):
        self.calls.append("pause_runtime")

    def resume_runtime(self):
        self.calls.append("resume_runtime")

    def restart_runtime(self):
        self.calls.append("restart_runtime")

    def view_logs(self):
        self.calls.append("view_logs")

    def quit(self):
        self.calls.append("quit")


@pytest.fixture
def tray(qapp):
    controller = FakeController()
    tray = LauncherTray(controller)
    yield tray, controller
    tray.hide()
    tray.deleteLater()


class TestMenu:
    def test_menu_offers_every_mandated_entry(self, tray):
        widget, _ = tray
        labels = [
            action.text()
            for action in widget.contextMenu().actions()
            if action.text()
        ]
        for expected in (
            "Open Dashboard",
            "Pause Runtime",
            "Resume Runtime",
            "Restart Runtime",
            "View Logs",
            "Exit",
        ):
            assert expected in labels

    def test_every_action_reaches_the_controller(self, tray):
        widget, controller = tray
        for key, call in (
            ("open", "open_dashboard"),
            ("pause", "pause_runtime"),
            ("restart", "restart_runtime"),
            ("logs", "view_logs"),
            ("exit", "quit"),
        ):
            widget.action(key).trigger()
            assert controller.calls[-1] == call

    def test_resume_action_when_paused(self, tray):
        widget, controller = tray
        controller.set_state("paused", "paused")
        widget.refresh()
        widget.action("resume").trigger()
        assert controller.calls[-1] == "resume_runtime"


class TestStatusIndicator:
    def test_tooltip_names_every_child_state(self, tray):
        widget, _ = tray
        widget.refresh()
        tip = widget.toolTip()
        assert tip.startswith("PAIOS — ok")
        assert "daemon running" in tip
        assert "gui stopped" in tip

    def test_status_action_tracks_overall_state(self, tray):
        widget, controller = tray
        controller.set_state("degraded", "failed")
        widget.refresh()
        texts = [a.text() for a in widget.contextMenu().actions()]
        assert "Status: degraded" in texts

    def test_pause_resume_enabled_state_follows_daemon(self, tray):
        widget, controller = tray
        widget.refresh()
        assert widget.action("pause").isEnabled()
        assert not widget.action("resume").isEnabled()
        controller.set_state("paused", "paused")
        widget.refresh()
        assert not widget.action("pause").isEnabled()
        assert widget.action("resume").isEnabled()

    def test_icon_exists_for_every_state(self, qapp):
        for state in STATE_COLORS:
            assert not build_status_icon(state).isNull()
        assert not build_status_icon("unknown-state").isNull()

    def test_tooltip_helper_is_qt_free(self):
        text = status_tooltip(
            "paused", {"daemon": {"state": "paused"}}
        )
        assert text == "PAIOS — paused (daemon paused)"

    def test_monitoring_timer_starts_and_stops(self, tray):
        widget, _ = tray
        widget.start_monitoring()
        assert widget._timer.isActive()
        widget.stop_monitoring()
        assert not widget._timer.isActive()
