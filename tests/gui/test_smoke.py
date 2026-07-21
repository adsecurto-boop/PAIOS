"""GUI smoke tests: the window over a live server, rendered offscreen.

No business assertions — these prove the presentation works: pages
build, refresh fills them from REST, actions round-trip, connection loss
degrades to the banner instead of a crash.
"""

from paios_gui import GuiConfig
from paios_gui.dialogs import DisturberDialog, NameDescriptionDialog
from paios_gui.main_window import MainWindow

from tests.gui.conftest import unreachable_client
from tests.gui.test_client import drive_event_via_rest


class TestDashboard:
    def test_refresh_fills_every_section(self, window):
        window.refresh_now()
        assert window.online is True
        sections = window.dashboard.sections
        for title in (
            "Time", "Status", "Current Event", "Current Context",
            "Today's Goals", "Today's Projects", "Recommendations",
            "Deep Work", "Health", "Resources", "Study", "Learning",
            "Recent Reflections", "Disturbers", "Notifications",
        ):
            assert title in sections
        assert "Current time: 2026-07-21" in sections["Time"].body_text()
        assert "Kernel:" in sections["Status"].body_text()
        assert "Idle — no running event." in (
            sections["Current Event"].body_text()
        )
        assert "Energy" in sections["Resources"].body_text()
        assert "just now" not in window.dashboard.footer.text()
        assert "online" in window.dashboard.footer.text()

    def test_footer_shows_refresh_interval(self, window):
        window.refresh_now()
        assert "refresh every 60s" in window.dashboard.footer.text()


class TestNavigation:
    def test_all_pages_open_and_refresh(self, window):
        names = [
            window.navigation.item(i).text()
            for i in range(window.navigation.count())
        ]
        assert names == [
            "Dashboard", "Goals", "Projects", "Events", "Resources",
            "Knowledge", "Learning", "History", "Settings", "Refresh",
        ]
        for row in range(9):
            window.navigation.setCurrentRow(row)
            assert window.pages.currentIndex() == row
        # The trailing Refresh entry refreshes and bounces back.
        window.navigation.setCurrentRow(9)
        assert window.pages.currentIndex() == 8

    def test_shortcut_objects_installed(self, window):
        from PySide6.QtGui import QShortcut

        sequences = {
            shortcut.key().toString()
            for shortcut in window.findChildren(QShortcut)
        }
        assert {"F5", "Ctrl+R", "Ctrl+1", "Ctrl+9"} <= sequences


class TestActions:
    def test_create_goal_action_appears_after_refresh(self, window):
        window.run_action(
            lambda: window.client.create_goal("Ship GUI", "M13"),
            "Goal created: Ship GUI",
        )
        assert window.online is True
        goals_page = window._page_list[1][1]
        goals_page.refresh(window.client)
        names = [row["name"] for row in goals_page._rows]
        assert "Ship GUI" in names
        assert "Goal created: Ship GUI" in (
            window.dashboard.notice_log.notices()
        )

    def test_event_lifecycle_from_events_page(self, window, client):
        event_id = drive_event_via_rest(client)
        window.navigation.setCurrentRow(3)  # Events
        events_page = window.current_page()
        assert any(row["event_id"] == event_id for row in events_page._rows)
        window.run_action(
            lambda: client.start_event(event_id), "Event started"
        )
        window.navigation.setCurrentRow(0)
        window.refresh_now()
        current = window.dashboard.sections["Current Event"].body_text()
        assert "Idle" not in current
        window.run_action(
            lambda: client.complete_event(event_id, "done"), "Event completed"
        )

    def test_rejected_action_notifies_without_crash(self, window):
        window.run_action(
            lambda: window.client.start_event("missing"), "never shown"
        )
        notices = window.dashboard.notice_log.notices()
        assert any("Rejected:" in notice for notice in notices)
        assert window.online is True

    def test_report_disturber_roundtrip(self, window):
        dialog = DisturberDialog()
        dialog.description_edit.setText("Phone call")
        values = dialog.values()
        window.run_action(
            lambda: window.client.report_disturber(**values),
            "Disturbance reported",
        )
        window.refresh_now()
        disturbers = window.dashboard.sections["Disturbers"].body_text()
        assert "Phone call" in disturbers


class TestDialogs:
    def test_name_description_values(self, qapp):
        dialog = NameDescriptionDialog("New goal")
        dialog.name_edit.setText("  A goal  ")
        dialog.description_edit.setText("why")
        assert dialog.values() == {"name": "A goal", "description": "why"}


class TestConnectionLoss:
    def test_offline_banner_and_recovery_path(self, qapp):
        gui_config = GuiConfig(base_url="http://127.0.0.1:9")
        window = MainWindow(unreachable_client(), gui_config)
        try:
            window.refresh_now()  # must not raise
            assert window.online is False
            assert window.banner.isHidden() is False
            assert "OFFLINE" in window.banner.text()
            assert "OFFLINE" in window.dashboard.footer.text()
            # Actions while offline degrade the same way.
            window.run_action(
                lambda: window.client.create_goal("x"), "never"
            )
            assert window.online is False
        finally:
            window.close()
            window.deleteLater()

    def test_reconnect_flips_banner_back(self, window):
        window._set_online(False, "down")
        assert window.banner.isHidden() is False
        window.refresh_now()
        assert window.online is True
        assert window.banner.isHidden() is True
