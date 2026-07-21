"""End-to-end: the observer over a real Application, and the CLI.

Integration drives the real stack (seeded store -> Application -> bus)
and asserts notifications appear as side effects only — every
Application behaviour is exercised through its existing public API.
"""

import io

import pytest

from paios.application.application import Application
from paios.application.config import ApplicationConfig
from paios.cli.main import main
from paios.notifications import NotificationManager, NullProvider
from paios.repositories.factory import RepositoryFactory
from paios.runtime.clock import ManualClock

from tests.application.conftest import T0, seed_rest_scenario
from tests.notifications.conftest import RecordingProvider


@pytest.fixture
def started_app(tmp_path):
    data_dir = tmp_path / "data"
    factory = RepositoryFactory(data_dir)
    factory.initialize()
    seed_rest_scenario(factory)
    application = Application(
        ApplicationConfig(data_dir=data_dir, clock=ManualClock(T0))
    )
    application.start()
    yield application
    if application.started:
        application.stop()


@pytest.fixture
def observed(started_app):
    provider = RecordingProvider()
    manager = NotificationManager(providers=(provider,))
    components = started_app.components
    manager.attach(
        components.kernel.event_bus, started_at=components.clock.now()
    )
    return started_app, manager, provider


class TestApplicationIntegration:
    def test_tick_generates_recommendation_notification(self, observed):
        application, manager, provider = observed
        application.tick()
        messages = [n.message for n in provider.sent]
        assert "Application started" in messages
        assert "Time progressed" in messages
        assert any("rest to recover" in m for m in messages)

    def test_accept_start_complete_flow(self, observed):
        application, manager, provider = observed
        application.tick()
        recommendation = application.active_recommendations()[0]
        application.accept_recommendation(recommendation.recommendation_id)
        event = application.list_events()[0]
        application.start_event(event.event_id)
        application.complete_event(event.event_id, actual_outcome="rested")
        messages = [n.message for n in provider.sent]
        assert any(m.startswith("Recommendation accepted:") for m in messages)
        assert any(m.startswith("Started:") for m in messages)
        assert any(m.endswith("completed") for m in messages)

    def test_disturber_is_critical_notification(self, observed):
        from paios.domain.enums import DisturberSeverity, DisturberType

        application, manager, provider = observed
        user = application.list_users()
        owner = (
            user[0].user_id
            if user
            else application.add_user("Tester").user_id
        )
        application.report_disturber(
            owner,
            DisturberType.WORK,
            "Urgent call",
            DisturberSeverity.HIGH,
        )
        critical = [
            n for n in provider.sent if n.severity.value == "Critical"
        ]
        assert critical, [n.message for n in provider.sent]
        assert "Unexpected interruption recorded" in critical[0].message

    def test_stop_notifies_application_stopped(self, observed):
        application, manager, provider = observed
        application.stop()
        assert provider.sent[-1].message == "Application stopped"

    def test_observer_leaves_application_behaviour_unchanged(
        self, started_app
    ):
        """Same actions with and without the observer -> same state."""
        manager = NotificationManager(providers=(NullProvider(),))
        components = started_app.components
        manager.attach(components.kernel.event_bus)
        started_app.tick()
        recommendation = started_app.active_recommendations()[0]
        started_app.accept_recommendation(recommendation.recommendation_id)
        events = started_app.list_events()
        assert len(events) == 1  # the flow behaves exactly as in M8-M12
        assert manager.history.unread_count > 0


def run_shell(tmp_path, lines, extra_argv=()):
    source = io.StringIO("".join(line + "\n" for line in lines))
    sink = io.StringIO()
    code = main(
        ["--data-dir", str(tmp_path / "cli-data"), *extra_argv, "shell"],
        input_stream=source,
        output_stream=sink,
    )
    return code, sink.getvalue()


class TestCli:
    def test_shell_notification_flow(self, tmp_path):
        code, output = run_shell(
            tmp_path,
            [
                "start",
                "notifications unread",
                "notifications",
                "notifications",
                "notifications history",
                "notifications clear",
                "notifications history",
                "stop",
            ],
        )
        assert code == 0
        # The console provider narrated the lifecycle (wall-clock times).
        assert "- [" in output and "[System] Application started" in output
        assert "Unread notifications: 1" in output
        assert "1 unread notification(s):" in output
        assert "* [" in output  # unread marker in the listing
        assert "No unread notifications." in output  # second call: marked
        assert "1 notification(s), 0 unread:" in output
        assert "Notification history cleared (1 dropped)." in output
        assert "No notifications recorded." in output
        assert "[System] Application stopped" in output

    def test_shell_tick_notifies_time_progress(self, tmp_path):
        code, output = run_shell(tmp_path, ["start", "tick", "stop"])
        assert code == 0
        assert "[Time] Time progressed" in output

    def test_quiet_hours_option_holds_console_output(self, tmp_path):
        code, output = run_shell(
            tmp_path,
            ["start", "notifications unread", "stop"],
            # Quiet for (almost) the whole day: the shell runs on the
            # wall clock, so the window must cover "now".
            extra_argv=["--quiet-hours", "00:00-23:59"],
        )
        assert code == 0
        # Nothing narrated to the console ("- [..]" lines are the
        # console provider's format), but history recorded it unread.
        assert "- [" not in output
        assert "Unread notifications: 1" in output

    def test_bad_quiet_hours_is_a_cli_error(self, tmp_path):
        code, output = run_shell(
            tmp_path, ["start"], extra_argv=["--quiet-hours", "bedtime"]
        )
        assert code == 1
        assert "Quiet hours must look like" in output

    def test_one_shot_notifications_command(self, tmp_path):
        sink = io.StringIO()
        code = main(
            ["--data-dir", str(tmp_path / "one-shot"), "notifications"],
            output_stream=sink,
        )
        assert code == 0
        # One-shot runs use the NullProvider; the just-started session
        # still records its own ApplicationStarted.
        assert "1 unread notification(s):" in sink.getvalue()
        assert "[System] Application started" in sink.getvalue()

    def test_help_lists_notification_commands(self, tmp_path):
        sink = io.StringIO()
        assert main(["help"], output_stream=sink) == 0
        text = sink.getvalue()
        for name in (
            "notifications",
            "notifications history",
            "notifications unread",
            "notifications clear",
        ):
            assert name in text
