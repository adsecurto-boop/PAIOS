"""Launcher lifecycle: config resolution, child specs, the headless
loop, the stop sentinel, and single-instance refusal at the entry."""

import os
import sys
from pathlib import Path

import pytest

from paios.system.config import SystemConfig

from paios_launcher import app as launcher_app
from paios_launcher.single_instance import SingleInstance
from paios_launcher.supervisor import ChildSpec, ChildState, Supervisor

PYTHON = sys.executable
SLEEPER = (PYTHON, "-c", "import time; time.sleep(10)")


def sleeper_spec(name):
    return ChildSpec(
        name=name, command=SLEEPER, stop_timeout_seconds=0.2
    )


class TestConfigResolution:
    def test_explicit_config_wins(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("data_dir: store\n", encoding="utf-8")
        system = launcher_app.resolve_config(str(config_file))
        assert system.source == str(config_file.resolve())
        assert system.data_dir == str(tmp_path / "store")

    def test_defaults_nest_logs_inside_data_dir(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("PAIOS_CONFIG", raising=False)
        system = launcher_app.resolve_config(None)
        assert system.source is None
        assert system.log_dir == str(Path(system.data_dir) / "logs")

    def test_install_dir_config_is_found(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("PAIOS_CONFIG", raising=False)
        target = tmp_path / "config" / "config.yaml"
        target.parent.mkdir()
        target.write_text("data_dir: d\n", encoding="utf-8")
        system = launcher_app.resolve_config(None)
        assert system.source == str(target.resolve())

    def test_missing_explicit_config_is_an_error(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            launcher_app.resolve_config(str(tmp_path / "nope.yaml"))


class TestChildSpecs:
    def system(self, tmp_path, source=None):
        return SystemConfig(
            data_dir=str(tmp_path / "data"),
            log_dir=str(tmp_path / "logs"),
            server_host="127.0.0.1",
            server_port=9911,
            gui_refresh_seconds=7,
            source=source,
        )

    def test_specs_cover_daemon_api_gui_in_start_order(self, tmp_path):
        specs = launcher_app.build_specs(
            self.system(tmp_path), "py.exe"
        )
        assert [spec.name for spec in specs] == ["daemon", "api", "gui"]

    def test_children_run_the_m16_public_surfaces(self, tmp_path):
        config_path = str(tmp_path / "config.yaml")
        specs = {
            spec.name: spec
            for spec in launcher_app.build_specs(
                self.system(tmp_path, source=config_path), "py.exe"
            )
        }
        assert specs["daemon"].command == (
            "py.exe", "-m", "paios.cli", "--config", config_path,
            "daemon", "run",
        )
        assert specs["api"].command == (
            "py.exe", "-m", "paios.cli", "--config", config_path, "serve"
        )
        gui = specs["gui"].command
        assert gui[:3] == ("py.exe", "-m", "paios_gui")
        assert "http://127.0.0.1:9911" in gui
        assert "7" in gui

    def test_no_config_source_means_no_config_flag(self, tmp_path):
        specs = launcher_app.build_specs(self.system(tmp_path), "py.exe")
        assert "--config" not in specs[0].command

    def test_gui_can_be_omitted(self, tmp_path):
        specs = launcher_app.build_specs(
            self.system(tmp_path), "py.exe", with_gui=False
        )
        assert [spec.name for spec in specs] == ["daemon", "api"]

    def test_daemon_pre_stop_writes_the_m16_sentinel(self, tmp_path):
        specs = launcher_app.build_specs(self.system(tmp_path), "py.exe")
        daemon = specs[0]
        daemon.pre_stop()
        assert (tmp_path / "logs" / "paios-daemon.stop").is_file()


class TestHeadlessLoop:
    def test_bounded_run_starts_polls_and_shuts_down(self, tmp_path):
        supervisor = Supervisor([sleeper_spec("a"), sleeper_spec("b")])
        code = launcher_app.run_headless(
            supervisor,
            tmp_path / "launcher.stop",
            max_polls=3,
            sleep=lambda seconds: None,
        )
        assert code == 0
        assert supervisor.child("a").state == ChildState.STOPPED
        assert supervisor.child("b").state == ChildState.STOPPED

    def test_stop_sentinel_ends_the_loop_and_is_cleaned_up(self, tmp_path):
        sentinel = tmp_path / "launcher.stop"
        supervisor = Supervisor([sleeper_spec("a")])

        def create_sentinel_then_wait(_seconds):
            sentinel.write_text("stop", encoding="utf-8")

        code = launcher_app.run_headless(
            supervisor,
            sentinel,
            max_polls=50,
            sleep=create_sentinel_then_wait,
        )
        assert code == 0
        assert not sentinel.exists()
        assert supervisor.child("a").state == ChildState.STOPPED

    def test_stale_sentinel_is_cleared_before_the_run(self, tmp_path):
        sentinel = tmp_path / "launcher.stop"
        sentinel.write_text("stale", encoding="utf-8")
        supervisor = Supervisor([sleeper_spec("a")])
        launcher_app.run_headless(
            supervisor, sentinel, max_polls=2, sleep=lambda s: None
        )
        # Ran both polls (the stale file did not end the loop early)
        # and left no sentinel behind.
        assert not sentinel.exists()


class TestEntry:
    def config_args(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "data_dir: data\nlog_dir: logs\n", encoding="utf-8"
        )
        return config_file

    def test_second_instance_is_refused(self, tmp_path, monkeypatch):
        config_file = self.config_args(tmp_path)
        # A private mutex name so this test never collides with (or is
        # broken by) an actually-running PAIOS on the machine.
        mutex_name = f"PAIOS.Test.Entry.{os.getpid()}"
        monkeypatch.setenv("PAIOS_LAUNCHER_MUTEX", mutex_name)
        if os.name == "nt":
            guard = SingleInstance(name=mutex_name).acquire()
        else:
            guard = SingleInstance(
                lock_file=tmp_path / "logs" / "paios-launcher.lock"
            ).acquire()
        try:
            code = launcher_app.main(
                ["--no-tray", "--config", str(config_file)]
            )
        finally:
            guard.release()
        assert code == 2

    def test_stop_flag_writes_the_sentinel(self, tmp_path):
        config_file = self.config_args(tmp_path)
        code = launcher_app.main(["--stop", "--config", str(config_file)])
        assert code == 0
        assert (tmp_path / "logs" / "paios-launcher.stop").is_file()

    def test_missing_config_fails_cleanly(self, tmp_path):
        code = launcher_app.main(
            ["--no-tray", "--config", str(tmp_path / "nope.yaml")]
        )
        assert code == 1

    def test_launcher_logs_land_in_the_structured_log(self, tmp_path):
        config_file = self.config_args(tmp_path)
        launcher_app.main(["--stop", "--config", str(config_file)])
        log_file = tmp_path / "logs" / "paios-launcher.log"
        assert log_file.is_file()

    def test_crash_hook_writes_a_report(self, tmp_path, monkeypatch):
        system = SystemConfig(
            data_dir=str(tmp_path), log_dir=str(tmp_path / "logs")
        )
        original_hook = sys.excepthook
        recorded = []
        monkeypatch.setattr(
            sys, "__excepthook__", lambda *a: recorded.append(a)
        )
        try:
            launcher_app.install_crash_hook(system)
            try:
                raise ValueError("synthetic launcher crash")
            except ValueError:
                sys.excepthook(*sys.exc_info())
        finally:
            sys.excepthook = original_hook
        reports = list(
            (tmp_path / "logs" / "crashes").glob(
                "paios-crash-launcher-*.log"
            )
        )
        assert len(reports) == 1
        assert "synthetic launcher crash" in reports[0].read_text(
            encoding="utf-8"
        )
        assert recorded  # the default hook still ran
