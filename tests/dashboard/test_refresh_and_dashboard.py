"""Refresh loop behavior, dashboard startup/shutdown, CLI entry points,
and the forbidden-import audit."""

import ast
from io import StringIO
from pathlib import Path

import pytest

import paios.dashboard as dashboard_package
from paios.cli.exceptions import CommandArgumentError
from paios.cli.main import main
from paios.dashboard import ALLOWED_INTERVALS, Dashboard, DashboardConfig
from paios.dashboard.refresh import CLEAR_SCREEN, CURSOR_HOME, RefreshLoop


class FakeTerminal(StringIO):
    def isatty(self) -> bool:
        return True


class TestRefreshLoop:
    def test_zero_interval_renders_single_frame(self):
        out = StringIO()
        loop = RefreshLoop(0, out, sleep=lambda s: None)
        assert loop.run(lambda: "FRAME") == "single-frame"
        assert loop.frames_rendered == 1
        assert out.getvalue() == "FRAME\n"

    def test_max_frames_bounds_the_loop_and_sleeps_the_interval(self):
        slept: list[float] = []
        loop = RefreshLoop(5, StringIO(), sleep=slept.append)
        assert loop.run(lambda: "F", max_frames=3) == "max-frames"
        assert loop.frames_rendered == 3
        assert slept == [5, 5]

    def test_keyboard_interrupt_exits_cleanly(self):
        def interrupt(_seconds):
            raise KeyboardInterrupt

        loop = RefreshLoop(1, StringIO(), sleep=interrupt)
        assert loop.run(lambda: "F") == "interrupted"
        assert loop.frames_rendered == 1

    def test_no_ansi_codes_on_non_terminal_streams(self):
        out = StringIO()
        RefreshLoop(0, out, sleep=lambda s: None).run(lambda: "F")
        assert "\x1b" not in out.getvalue()

    def test_terminal_gets_single_write_home_redraw(self):
        out = FakeTerminal()
        loop = RefreshLoop(1, out, sleep=lambda s: None)
        loop.run(lambda: "F", max_frames=2)
        text = out.getvalue()
        assert text.count(CLEAR_SCREEN) == 1  # full clear only once
        assert text.count(CURSOR_HOME) == 2  # every frame homes the cursor
        assert "\x1b[?25h" in text  # cursor restored on exit


class TestDashboardLifecycle:
    def test_render_once_needs_no_streams(self, dash_app):
        frame = Dashboard(dash_app).render_once()
        assert "PAIOS DASHBOARD" in frame

    def test_run_writes_goodbye_on_exit(self, dash_app):
        out = StringIO()
        dashboard = Dashboard(
            dash_app,
            DashboardConfig(refresh_seconds=0),
            output_stream=out,
        )
        assert dashboard.run() == "single-frame"
        assert out.getvalue().endswith("Dashboard closed.\n")

    def test_ctrl_c_shuts_down_cleanly(self, dash_app):
        def interrupt(_seconds):
            raise KeyboardInterrupt

        out = StringIO()
        dashboard = Dashboard(
            dash_app,
            DashboardConfig(refresh_seconds=1),
            output_stream=out,
            sleep=interrupt,
        )
        assert dashboard.run() == "interrupted"
        assert dashboard.frames_rendered == 1
        assert "Dashboard closed." in out.getvalue()

    def test_config_rejects_unsupported_interval(self):
        with pytest.raises(ValueError):
            DashboardConfig(refresh_seconds=2)
        for interval in ALLOWED_INTERVALS:
            DashboardConfig(refresh_seconds=interval)


class TestCliEntryPoints:
    def test_one_shot_dashboard_renders_and_exits(self, tmp_path):
        out = StringIO()
        exit_code = main(
            ["--data-dir", str(tmp_path / "data"), "dashboard", "0"],
            output_stream=out,
        )
        assert exit_code == 0
        text = out.getvalue()
        assert "PAIOS DASHBOARD" in text
        assert text.endswith("Dashboard closed.\n")

    def test_one_shot_rejects_bad_interval(self, tmp_path):
        out = StringIO()
        exit_code = main(
            ["--data-dir", str(tmp_path / "data"), "dashboard", "2"],
            output_stream=out,
        )
        assert exit_code == 1
        assert "Refresh must be one of" in out.getvalue()

    def test_shell_dashboard_returns_to_prompt(self, tmp_path):
        source = StringIO("start\ndashboard 0\nstatus\nexit\n")
        out = StringIO()
        exit_code = main(
            ["--data-dir", str(tmp_path / "data"), "shell"],
            input_stream=source,
            output_stream=out,
        )
        assert exit_code == 0
        text = out.getvalue()
        assert "PAIOS DASHBOARD" in text
        assert "Dashboard closed." in text
        assert "State:             Running" in text  # shell kept working
        assert "Goodbye." in text

    def test_shell_dashboard_requires_started_application(self, tmp_path):
        source = StringIO("dashboard 0\nexit\n")
        out = StringIO()
        main(
            ["--data-dir", str(tmp_path / "data"), "shell"],
            input_stream=source,
            output_stream=out,
        )
        assert "Error:" in out.getvalue()

    def test_dashboard_config_validation_helper(self):
        from paios.cli.commands import build_dashboard_config

        assert build_dashboard_config([]).refresh_seconds == 1
        assert build_dashboard_config(["5"]).refresh_seconds == 5
        with pytest.raises(CommandArgumentError):
            build_dashboard_config(["fast"])
        with pytest.raises(CommandArgumentError):
            build_dashboard_config(["3"])


FORBIDDEN_IMPORT_PREFIXES = (
    "paios.runtime",
    "paios.scheduler",
    "paios.decision_engine",
    "paios.learning",
    "paios.repositories",
    "paios.infrastructure",
    "paios.domain",
    "paios.daemon",
    "paios.cli",
)


class TestForbiddenImports:
    def test_dashboard_imports_only_application_and_stdlib(self):
        package_dir = Path(dashboard_package.__file__).parent
        for module_path in package_dir.glob("*.py"):
            tree = ast.parse(module_path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                for name in names:
                    assert not name.startswith(FORBIDDEN_IMPORT_PREFIXES), (
                        f"{module_path.name} imports forbidden {name!r}"
                    )
                    if name.startswith("paios"):
                        assert name.startswith(
                            ("paios.application", "paios.dashboard")
                        ), f"{module_path.name} imports {name!r}"
