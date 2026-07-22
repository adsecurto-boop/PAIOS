"""Supervisor behaviour with real (tiny) child processes."""

import sys
import time

from paios_launcher.supervisor import (
    ChildSpec,
    ChildState,
    RestartPolicy,
    Supervisor,
    SupervisorEvent,
)

PYTHON = sys.executable

#: A child that runs "forever" (10 s dwarfs any test timeout here).
SLEEPER = (PYTHON, "-c", "import time; time.sleep(10)")
#: A child that dies immediately with a non-zero code.
CRASHER = (PYTHON, "-c", "import sys; print('boom'); sys.exit(3)")
#: A child that exits cleanly at once.
CLEAN_EXIT = (PYTHON, "-c", "print('bye')")


def wait_for(predicate, timeout=10.0, interval=0.05):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(interval)
    raise AssertionError("condition not met within timeout")


def spec(name, command, **kwargs):
    kwargs.setdefault("stop_timeout_seconds", 0.2)
    return ChildSpec(name=name, command=command, **kwargs)


class FakeClock:
    def __init__(self):
        self.value = 1000.0

    def __call__(self):
        return self.value


class TestLifecycle:
    def test_start_all_runs_children_in_order(self):
        events = []
        supervisor = Supervisor(
            [spec("a", SLEEPER), spec("b", SLEEPER)],
            on_event=events.append,
        )
        supervisor.start_all()
        try:
            assert [e.kind for e in events] == ["started", "started"]
            assert [e.child for e in events] == ["a", "b"]
            assert supervisor.overall_state() == "ok"
            status = supervisor.status()
            assert status["a"]["state"] == "running"
            assert status["a"]["pid"] is not None
        finally:
            supervisor.shutdown()

    def test_shutdown_stops_everything_in_reverse_order(self):
        events = []
        supervisor = Supervisor(
            [spec("a", SLEEPER), spec("b", SLEEPER)],
            on_event=events.append,
        )
        supervisor.start_all()
        supervisor.shutdown()
        stopped = [e.child for e in events if e.kind == "stopped"]
        assert stopped == ["b", "a"]
        assert supervisor.overall_state() == "stopped"
        for child in ("a", "b"):
            assert supervisor.child(child).state == ChildState.STOPPED
            assert supervisor.child(child).process is None

    def test_pre_stop_hook_enables_graceful_exit(self, tmp_path):
        """A child that watches for a sentinel (the daemon pattern)
        exits on its own within the stop timeout — no terminate."""
        sentinel = tmp_path / "stop.flag"
        watcher = (
            PYTHON,
            "-c",
            "import os,sys,time\n"
            "for _ in range(200):\n"
            "    if os.path.exists(sys.argv[1]):\n"
            "        sys.exit(0)\n"
            "    time.sleep(0.05)\n"
            "sys.exit(9)",
            str(sentinel),
        )
        supervisor = Supervisor(
            [
                ChildSpec(
                    name="daemon",
                    command=watcher,
                    pre_stop=lambda: sentinel.write_text("stop"),
                    stop_timeout_seconds=8.0,
                )
            ]
        )
        supervisor.start_all()
        started = time.monotonic()
        supervisor.shutdown()
        # Fast because the hook fired, not because we killed it.
        assert time.monotonic() - started < 8.0
        assert supervisor.child("daemon").state == ChildState.STOPPED

    def test_clean_exit_is_not_restarted(self):
        supervisor = Supervisor([spec("gui", CLEAN_EXIT)])
        supervisor.start_all()
        event = wait_for(
            lambda: next(iter(supervisor.poll()), None)
        )
        assert event.kind == "exited"
        assert supervisor.child("gui").state == ChildState.STOPPED
        # Further polls stay quiet.
        assert supervisor.poll() == []


class TestCrashAndRestart:
    def test_crash_is_detected_restarted_and_logged(self, tmp_path):
        clock = FakeClock()
        out = tmp_path / "crasher.out"
        supervisor = Supervisor(
            [
                spec(
                    "api",
                    CRASHER,
                    policy=RestartPolicy(
                        max_restarts=5, backoff_seconds=(2.0,)
                    ),
                    output_path=out,
                )
            ],
            crash_dir=tmp_path / "crashes",
            now=clock,
        )
        supervisor.start_all()
        event = wait_for(lambda: next(iter(supervisor.poll()), None))
        assert event.kind == "crashed"
        assert "exit code 3" in event.detail
        assert supervisor.child("api").state == ChildState.CRASHED
        assert supervisor.overall_state() == "degraded"

        # Crash report written, with the child's output tail inside.
        reports = list((tmp_path / "crashes").glob("paios-crash-api-*.log"))
        assert len(reports) == 1
        content = reports[0].read_text(encoding="utf-8")
        assert "exit code 3" in content
        assert "boom" in content

        # Not restarted before the backoff elapses…
        assert supervisor.poll() == []
        # …restarted after it.
        clock.value += 2.5
        event = wait_for(lambda: next(iter(supervisor.poll()), None))
        assert event.kind == "restarted"
        assert supervisor.child("api").restart_count == 1
        supervisor.shutdown()

    def test_restart_budget_exhaustion_marks_failed(self, tmp_path):
        clock = FakeClock()
        supervisor = Supervisor(
            [
                spec(
                    "api",
                    CRASHER,
                    policy=RestartPolicy(
                        max_restarts=2,
                        window_seconds=300,
                        backoff_seconds=(0.0,),
                    ),
                )
            ],
            crash_dir=tmp_path / "crashes",
            now=clock,
        )
        supervisor.start_all()
        kinds = []
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            for event in supervisor.poll():
                kinds.append(event.kind)
            if kinds and kinds[-1] == "failed":
                break
            time.sleep(0.05)
        assert kinds == ["crashed", "restarted", "crashed", "restarted",
                         "failed"]
        assert supervisor.child("api").state == ChildState.FAILED
        assert supervisor.overall_state() == "degraded"

    def test_restart_window_expiry_refills_the_budget(self):
        clock = FakeClock()
        supervisor = Supervisor(
            [
                spec(
                    "api",
                    CRASHER,
                    policy=RestartPolicy(
                        max_restarts=1,
                        window_seconds=60,
                        backoff_seconds=(0.0,),
                    ),
                )
            ],
            now=clock,
        )
        supervisor.start_all()
        event = wait_for(lambda: next(iter(supervisor.poll()), None))
        assert event.kind == "crashed"
        event = wait_for(lambda: next(iter(supervisor.poll()), None))
        assert event.kind == "restarted"
        # Second crash inside the window: budget spent -> failed.
        event = wait_for(lambda: next(iter(supervisor.poll()), None))
        assert event.kind == "failed"
        # An hour later the window is clear again: manual restart works
        # and the next crash is once more restartable.
        clock.value += 3600
        supervisor.restart("api")
        event = wait_for(
            lambda: next(
                (e for e in supervisor.poll() if e.kind == "crashed"), None
            )
        )
        assert "restart in" in event.detail
        supervisor.shutdown()

    def test_restart_disabled_fails_immediately(self, tmp_path):
        supervisor = Supervisor(
            [spec("gui", CRASHER, restart_on_crash=False)],
            crash_dir=tmp_path / "crashes",
        )
        supervisor.start_all()
        event = wait_for(lambda: next(iter(supervisor.poll()), None))
        assert event.kind == "failed"
        assert "restart disabled" in event.detail


class TestRuntimeControls:
    def test_pause_stops_without_restart_then_resume(self):
        supervisor = Supervisor([spec("daemon", SLEEPER)])
        supervisor.start_all()
        supervisor.pause("daemon")
        assert supervisor.child("daemon").state == ChildState.PAUSED
        assert supervisor.overall_state() == "paused"
        # Polling a paused child never revives it.
        assert supervisor.poll() == []
        supervisor.resume("daemon")
        assert supervisor.child("daemon").state == ChildState.RUNNING
        assert supervisor.overall_state() == "ok"
        supervisor.shutdown()

    def test_restart_replaces_the_process(self):
        supervisor = Supervisor([spec("daemon", SLEEPER)])
        supervisor.start_all()
        first_pid = supervisor.child("daemon").pid
        supervisor.restart("daemon")
        second_pid = supervisor.child("daemon").pid
        assert second_pid is not None
        assert second_pid != first_pid
        assert supervisor.child("daemon").state == ChildState.RUNNING
        supervisor.shutdown()

    def test_resume_running_child_is_a_no_op(self):
        supervisor = Supervisor([spec("daemon", SLEEPER)])
        supervisor.start_all()
        pid = supervisor.child("daemon").pid
        supervisor.resume("daemon")
        assert supervisor.child("daemon").pid == pid
        supervisor.shutdown()


class TestEventSafety:
    def test_observer_exceptions_never_disturb_supervision(self):
        def bad_observer(event: SupervisorEvent) -> None:
            raise RuntimeError("observer bug")

        supervisor = Supervisor(
            [spec("a", SLEEPER)], on_event=bad_observer
        )
        supervisor.start_all()  # would raise if the observer leaked
        assert supervisor.overall_state() == "ok"
        supervisor.shutdown()
