"""M14 desktop integration: center model, poll-diff watcher, window."""

from paios_gui.notifications import (
    DashboardWatcher,
    GuiNotification,
    NotificationCenter,
)

from tests.gui.test_client import drive_event_via_rest


def payload(recommendations=(), disturbers=(), event=None, context="Idle"):
    return {
        "current_time": "2026-07-21T09:00:00",
        "recommendations": [
            {"recommendation_id": rid, "reason": f"reason {rid}"}
            for rid in recommendations
        ],
        "active_disturbers": [
            {
                "event_disturber_id": did,
                "severity": severity,
                "description": f"disturbance {did}",
            }
            for did, severity in disturbers
        ],
        "current_event": event,
        "current_context": {"execution_context": context},
    }


class TestNotificationCenter:
    def test_unread_mark_clear(self):
        center = NotificationCenter()
        for index in range(3):
            center.add(GuiNotification(message=f"m{index}", category="App"))
        assert center.unread_count == 3
        assert [n.message for n in center.entries()] == ["m2", "m1", "m0"]
        assert center.mark_all_read() == 3
        assert center.unread_count == 0
        assert center.clear() == 3
        assert center.entries() == []

    def test_bounded(self):
        center = NotificationCenter(limit=2)
        for index in range(4):
            center.add(GuiNotification(message=f"m{index}", category="App"))
        assert [n.message for n in center.entries()] == ["m3", "m2"]


class TestDashboardWatcher:
    def test_first_observation_is_silent_baseline(self):
        watcher = DashboardWatcher()
        assert watcher.observe(payload(recommendations=["r1"])) == []

    def test_new_recommendation_and_disturber_detected(self):
        watcher = DashboardWatcher()
        watcher.observe(payload(recommendations=["r1"]))
        fresh = watcher.observe(
            payload(
                recommendations=["r1", "r2"],
                disturbers=[("d1", "High")],
            )
        )
        messages = sorted(n.message for n in fresh)
        assert messages == [
            "Disturbance: [High] disturbance d1",
            "Recommendation: reason r2",
        ]
        kinds = {n.category: n.kind for n in fresh}
        assert kinds["Disturbance"] == "error"

    def test_unchanged_state_reports_nothing(self):
        watcher = DashboardWatcher()
        snapshot = payload(recommendations=["r1"])
        watcher.observe(snapshot)
        assert watcher.observe(snapshot) == []

    def test_running_event_and_context_changes(self):
        watcher = DashboardWatcher()
        watcher.observe(payload())
        fresh = watcher.observe(
            payload(
                event={"event_id": "e1", "description": "Deep work"},
                context="EventExecutionContext",
            )
        )
        messages = {n.message for n in fresh}
        assert "Now running: Deep work" in messages
        assert "Context changed: EventExecutionContext" in messages


class TestWindowIntegration:
    def test_refresh_feeds_center_and_badge(self, window, client):
        window.refresh_now()  # baseline
        baseline_unread = window.notification_center.unread_count
        client._request("POST", "/tick", {})  # new recommendation appears
        window.refresh_now()
        assert window.notification_center.unread_count > baseline_unread
        badge = window.navigation.item(window._notifications_row).text()
        assert badge.startswith("Notifications (")

    def test_notifications_page_lists_and_marks_read(self, window, client):
        window.refresh_now()
        client._request("POST", "/tick", {})
        window.refresh_now()
        window.navigation.setCurrentRow(window._notifications_row)
        page = window.current_page()
        assert page.table.rowCount() == len(
            window.notification_center.entries()
        )
        page._on_mark_read()
        assert window.notification_center.unread_count == 0
        assert (
            window.navigation.item(window._notifications_row).text()
            == "Notifications"
        )
        page._on_clear()
        assert window.notification_center.entries() == []

    def test_watcher_notices_event_started_via_rest(self, window, client):
        window.refresh_now()  # baseline
        event_id = drive_event_via_rest(client)
        client.start_event(event_id)
        window.refresh_now()
        messages = [
            n.message for n in window.notification_center.entries()
        ]
        assert any(m.startswith("Now running:") for m in messages)

    def test_action_feedback_lands_in_center(self, window):
        window.run_action(
            lambda: window.client.create_goal("Notify me", "M14"),
            "Goal created: Notify me",
        )
        messages = [
            n.message for n in window.notification_center.entries()
        ]
        assert "Goal created: Notify me" in messages
