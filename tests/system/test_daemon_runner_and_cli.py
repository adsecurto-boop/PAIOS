"""Daemon process runner (foreground, pid/stop files) and the M16 CLI
surfaces (init, health, backup, daemon status, gui, config option)."""

import io
import os
import threading

from paios.cli.main import main
from paios.system import daemon_runner
from paios.system.config import SystemConfig, generate_default_config


def system_for(tmp_path, **overrides) -> SystemConfig:
    defaults = dict(
        data_dir=str(tmp_path / "data"),
        log_dir=str(tmp_path / "logs"),
        backup_dir=str(tmp_path / "backups"),
        daemon_tick_seconds=0.01,
        backup_enabled=True,
        backup_interval_hours=24.0,
    )
    defaults.update(overrides)
    return SystemConfig(**defaults)


class TestForegroundRunner:
    def test_bounded_run_ticks_and_cleans_up(self, tmp_path):
        config = system_for(tmp_path)
        sink = io.StringIO()
        code = daemon_runner.run_foreground(
            config, max_iterations=3, output=sink
        )
        assert code == 0
        text = sink.getvalue()
        assert "PAIOS daemon running" in text
        assert "PAIOS daemon stopped." in text
        assert not daemon_runner.pid_file(config).exists()
        # The backup policy ran inside the loop: one due backup taken.
        assert len(list((tmp_path / "backups").glob("*.zip"))) == 1

    def test_stop_file_ends_the_loop(self, tmp_path):
        config = system_for(tmp_path)
        sink = io.StringIO()
        finished = threading.Event()

        def run() -> None:
            daemon_runner.run_foreground(config, output=sink)
            finished.set()

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        # Let it begin, then request a graceful stop via the sentinel.
        deadline_hit = finished.wait(0.2)
        assert not deadline_hit
        daemon_runner.stop_file(config).parent.mkdir(
            parents=True, exist_ok=True
        )
        daemon_runner.stop_file(config).write_text("stop", encoding="utf-8")
        assert finished.wait(10), "daemon did not honour the stop file"
        assert not daemon_runner.pid_file(config).exists()
        assert not daemon_runner.stop_file(config).exists()

    def test_observers_are_built_and_detached(self, tmp_path):
        config = system_for(tmp_path, backup_enabled=False)
        seen = {}

        def build(application):
            seen["bus"] = application.components.kernel.event_bus
            return lambda: seen.setdefault("detached", True)

        daemon_runner.run_foreground(
            config, build_observers=build, max_iterations=1, output=io.StringIO()
        )
        assert "bus" in seen
        assert seen.get("detached") is True


class TestProcessBookkeeping:
    def test_status_without_pid_file(self, tmp_path):
        config = system_for(tmp_path)
        assert daemon_runner.daemon_status(config) == (
            "not running (no pid file)"
        )

    def test_stale_pid_file_detected(self, tmp_path):
        config = system_for(tmp_path)
        daemon_runner.pid_file(config).parent.mkdir(parents=True)
        daemon_runner.pid_file(config).write_text("999999999")
        assert "stale pid file" in daemon_runner.daemon_status(config)
        assert "not running" in daemon_runner.stop_background(config)
        assert not daemon_runner.pid_file(config).exists()

    def test_current_process_is_alive(self):
        assert daemon_runner.process_alive(os.getpid()) is True
        assert daemon_runner.process_alive(999999999) is False


def run_cli(*arguments, cwd=None):
    sink = io.StringIO()
    code = main(list(arguments), output_stream=sink)
    return code, sink.getvalue()


class TestCliSurfaces:
    def test_init_creates_config_and_directories(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("PAIOS_CONFIG", raising=False)
        code, output = run_cli("init")
        assert code == 0
        assert (tmp_path / "config" / "config.yaml").is_file()
        assert (tmp_path / "data").is_dir()
        assert (tmp_path / "logs").is_dir()
        assert (tmp_path / "backups").is_dir()
        assert "PAIOS initialized." in output
        # Second run is idempotent and adopts the existing file.
        code, output = run_cli("init")
        assert code == 0
        assert "Using configuration" in output

    def test_health_command(self, tmp_path):
        code, output = run_cli("--data-dir", str(tmp_path / "data"), "health")
        assert code == 0
        for component in (
            "repositories", "application", "scheduler", "clock",
            "event bus", "daemon", "api",
        ):
            assert component in output
        assert "All checks passed." in output

    def test_backup_cycle_via_cli(self, tmp_path):
        data_dir = str(tmp_path / "data")
        # Materialize a store first.
        code, _ = run_cli("--data-dir", data_dir, "status")
        assert code == 0
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            f"data_dir: {data_dir}\n"
            f"log_dir: {tmp_path / 'logs'}\n"
            f"backup_dir: {tmp_path / 'backups'}\n",
            encoding="utf-8",
        )
        base = ("--config", str(config_file))
        code, output = run_cli(*base, "backup", "now")
        assert code == 0 and "Backup created" in output
        code, output = run_cli(*base, "backup", "list")
        assert code == 0 and "paios-backup-" in output
        archive_name = output.strip().splitlines()[-1]
        code, output = run_cli(*base, "backup", "restore", archive_name)
        assert code == 0 and "Restored" in output
        exported = tmp_path / "export.zip"
        code, output = run_cli(*base, "backup", "export", str(exported))
        assert code == 0 and exported.is_file()
        code, output = run_cli(*base, "backup", "import", str(exported))
        assert code == 0 and "Restored" in output
        code, output = run_cli(*base, "backup", "bogus")
        assert code == 1 and "Usage" in output

    def test_daemon_status_via_cli(self, tmp_path):
        code, output = run_cli(
            "--data-dir", str(tmp_path / "data"), "daemon", "status"
        )
        assert code == 0
        assert "Daemon: not running" in output

    def test_gui_launch_is_delegated(self, tmp_path, monkeypatch):
        import importlib

        cli_main = importlib.import_module("paios.cli.main")
        commands = []
        monkeypatch.setattr(
            cli_main,
            "_launch_detached",
            lambda command: commands.append(command) or 4242,
        )
        code, output = run_cli(
            "--data-dir", str(tmp_path / "data"), "gui"
        )
        assert code == 0
        assert "GUI launched (pid 4242)" in output
        command = commands[0]
        assert command[1:3] == ["-m", "paios_gui"]
        assert "--url" in command and "--log-dir" in command

    def test_config_option_drives_data_dir(self, tmp_path):
        target = generate_default_config(
            tmp_path / "config" / "config.yaml"
        )
        code, output = run_cli("--config", str(target), "status")
        assert code == 0
        assert (tmp_path / "data").is_dir()  # store created next to config

    def test_missing_config_is_an_error(self, tmp_path):
        code, output = run_cli("--config", str(tmp_path / "nope.yaml"), "help")
        assert code == 1
        assert "not found" in output

    def test_dashboard_interval_comes_from_config(self, tmp_path):
        # M18: the M16 `dashboard.refresh_seconds` knob is wired. A
        # config value of 0 renders exactly one frame and exits cleanly.
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            f"data_dir: {tmp_path / 'data'}\n"
            f"log_dir: {tmp_path / 'logs'}\n"
            "dashboard:\n"
            "  refresh_seconds: 0\n",
            encoding="utf-8",
        )
        code, output = run_cli("--config", str(config_file), "dashboard")
        assert code == 0
        assert "PAIOS DASHBOARD" in output or "TODAY" in output.upper()

    def test_invalid_config_dashboard_interval_is_a_clean_error(
        self, tmp_path
    ):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            f"data_dir: {tmp_path / 'data'}\n"
            f"log_dir: {tmp_path / 'logs'}\n"
            "dashboard:\n"
            "  refresh_seconds: 30\n",  # not in the allowed set
            encoding="utf-8",
        )
        code, output = run_cli("--config", str(config_file), "dashboard")
        assert code == 1
        assert "Refresh must be one of" in output

    def test_explicit_dashboard_argument_beats_config(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            f"data_dir: {tmp_path / 'data'}\n"
            f"log_dir: {tmp_path / 'logs'}\n"
            "dashboard:\n"
            "  refresh_seconds: 30\n",  # invalid, but overridden below
            encoding="utf-8",
        )
        code, _ = run_cli("--config", str(config_file), "dashboard", "0")
        assert code == 0

    def test_help_lists_m16_commands(self):
        code, output = run_cli("help")
        assert code == 0
        for name in ("init", "health", "gui", "daemon", "backup"):
            assert name in output
