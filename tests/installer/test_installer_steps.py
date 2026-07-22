"""Installer step behaviour with fake runner/registry ports.

Machine-touching operations (subprocess, winreg, real Desktop/Start
Menu) are observed through the ports; filesystem effects land in
tmp_path. One test creates a real venv to prove that step end to end.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from paios_installer.steps import (
    Installer,
    InstallerError,
    InstallLog,
    InstallOptions,
    RUN_VALUE_NAME,
    SHORTCUT_NAME,
    START_MENU_FOLDER,
    TASK_NAME,
    Uninstaller,
    shortcut_script,
)


class FakeRunner:
    """Records every command; scripted results per command head."""

    def __init__(self):
        self.calls = []
        self.results = {}
        self.side_effects = {}

    def script(self, key, returncode=0, stdout="", stderr=""):
        self.results[key] = SimpleNamespace(
            returncode=returncode, stdout=stdout, stderr=stderr
        )

    def on(self, key, effect):
        self.side_effects[key] = effect

    def __call__(self, command, **kwargs):
        self.calls.append((tuple(str(c) for c in command), kwargs))
        for key, effect in self.side_effects.items():
            if any(key in str(part) for part in command):
                effect()
        for key, result in self.results.items():
            if any(key in str(part) for part in command):
                return result
        return SimpleNamespace(returncode=0, stdout="3.12", stderr="")

    def commands(self):
        return [call[0] for call in self.calls]


class FakeRegistry:
    def __init__(self):
        self.values = {}

    def set_run_value(self, name, command):
        self.values[name] = command

    def delete_run_value(self, name):
        self.values.pop(name, None)

    def get_run_value(self, name):
        return self.values.get(name)


@pytest.fixture
def harness(tmp_path):
    install_dir = tmp_path / "install"
    payload = tmp_path / "payload"
    payload.mkdir()
    (payload / "paios-1.7.0-py3-none-any.whl").write_bytes(b"wheel")
    (payload / "PAIOS.exe").write_bytes(b"exe")
    runner = FakeRunner()
    registry = FakeRegistry()
    options = InstallOptions(
        install_dir=install_dir,
        payload_dir=payload,
        runtime_task=True,
    )
    log = InstallLog(
        tmp_path / "log" / "install.log", echo=lambda message: None
    )
    installer = Installer(
        options,
        runner=runner,
        registry=registry,
        log=log,
        desktop=tmp_path / "Desktop",
        start_menu=tmp_path / "StartMenu",
    )
    # The venv "exists" for the fake path; config appears when init runs.
    installer.venv_python.parent.mkdir(parents=True)
    installer.venv_python.write_bytes(b"")
    runner.on(
        "init",
        lambda: (
            installer.config_file.parent.mkdir(parents=True, exist_ok=True),
            installer.config_file.write_text("data_dir: ../data\n"),
        ),
    )
    return SimpleNamespace(
        installer=installer,
        runner=runner,
        registry=registry,
        options=options,
        tmp=tmp_path,
    )


class TestFullRun:
    def test_run_executes_every_step(self, harness):
        harness.installer.run()
        commands = harness.runner.commands()
        # Python version check, pip install, init, 2 shortcuts,
        # schtasks, health.
        assert any("pip" in c for command in commands for c in command)
        assert any("init" in command for command in commands)
        assert any("schtasks" in command[0] for command in commands)
        assert any("health" in command for command in commands)

    def test_wheel_installed_with_gui_extra(self, harness):
        harness.installer.run()
        pip_call = next(
            command for command in harness.runner.commands()
            if "install" in command
        )
        spec = pip_call[-1]
        assert "paios-1.7.0-py3-none-any.whl[gui]" in spec

    def test_no_gui_drops_the_extra(self, harness):
        harness.installer.options = harness.options.__class__(
            **{**harness.options.__dict__, "with_gui": False}
        )
        harness.installer.install_package()
        spec = harness.runner.commands()[-1][-1]
        assert spec.endswith(".whl")
        assert "[gui]" not in spec

    def test_launcher_exe_copied_from_payload(self, harness):
        harness.installer.place_launcher()
        assert harness.installer.launcher_exe.read_bytes() == b"exe"

    def test_layout_directories_created(self, harness):
        harness.installer.create_layout()
        for name in ("config", "data", "logs", "backups"):
            assert (harness.options.install_dir / name).is_dir()

    def test_install_log_written(self, harness):
        harness.installer.run()
        content = harness.installer.log.path.read_text(encoding="utf-8")
        assert "PAIOS installer" in content
        assert "PAIOS installed successfully." in content


class TestPythonCheck:
    def test_old_python_is_rejected(self, harness):
        harness.runner.script("version_info", stdout="3.10")
        harness.runner.results["version_info"] = SimpleNamespace(
            returncode=0, stdout="3.10", stderr=""
        )
        with pytest.raises(InstallerError, match="3.12"):
            harness.installer.check_python()

    def test_missing_python_is_a_clear_error(self, harness):
        def raise_oserror(command, **kwargs):
            raise OSError("not found")

        harness.installer.runner = raise_oserror
        with pytest.raises(InstallerError, match="Python not found"):
            harness.installer.check_python()


class TestShortcuts:
    def test_both_shortcuts_requested_via_powershell(self, harness):
        harness.installer.place_launcher()
        harness.installer.create_shortcuts()
        scripts = [
            command[-1]
            for command in harness.runner.commands()
            if command[0] == "powershell"
        ]
        assert len(scripts) == 2
        assert any(str(harness.tmp / "Desktop") in s for s in scripts)
        assert any(
            str(harness.tmp / "StartMenu" / START_MENU_FOLDER) in s
            for s in scripts
        )
        for script in scripts:
            assert str(harness.installer.launcher_exe) in script

    def test_shortcut_script_shape(self, tmp_path):
        script = shortcut_script(
            tmp_path / "PAIOS.lnk", tmp_path / "PAIOS.exe", tmp_path
        )
        assert "WScript.Shell" in script
        assert "CreateShortcut" in script
        assert "$s.Save()" in script

    def test_shortcuts_can_be_disabled(self, harness):
        harness.installer.options = harness.options.__class__(
            **{**harness.options.__dict__, "create_shortcuts": False}
        )
        harness.installer.create_shortcuts()
        assert not any(
            command[0] == "powershell"
            for command in harness.runner.commands()
        )

    def test_failed_shortcut_is_an_installer_error(self, harness):
        harness.runner.script("powershell", returncode=1, stderr="denied")
        with pytest.raises(InstallerError, match="shortcut"):
            harness.installer.create_shortcuts()


class TestStartupRegistration:
    def test_run_key_points_at_the_launcher(self, harness):
        harness.installer.place_launcher()
        harness.installer.register_startup()
        value = harness.registry.get_run_value(RUN_VALUE_NAME)
        assert value == f'"{harness.installer.launcher_exe}"'

    def test_without_launcher_exe_nothing_is_registered(self, harness):
        harness.installer.register_startup()
        assert harness.registry.get_run_value(RUN_VALUE_NAME) is None

    def test_runtime_task_uses_schtasks_onlogon(self, harness):
        harness.installer.register_runtime_task()
        command = next(
            command for command in harness.runner.commands()
            if command[0] == "schtasks"
        )
        assert "/SC" in command and "ONLOGON" in command
        assert TASK_NAME in command
        task_run = command[command.index("/TR") + 1]
        assert "daemon start" in task_run
        assert "--config" in task_run


class TestConfigGeneration:
    def test_config_generated_via_paios_init_from_install_root(
        self, harness
    ):
        harness.installer.generate_config()
        init_call = next(
            call for call in harness.runner.calls
            if "init" in call[0]
        )
        assert init_call[1]["cwd"] == str(harness.options.install_dir)
        assert harness.installer.config_file.is_file()

    def test_existing_config_is_never_overwritten(self, harness):
        harness.installer.config_file.parent.mkdir(parents=True)
        harness.installer.config_file.write_text("keep: me\n")
        harness.installer.generate_config()
        assert harness.installer.config_file.read_text() == "keep: me\n"
        assert not any(
            "init" in command for command in harness.runner.commands()
        )


class TestVenvCreation:
    def test_real_venv_is_created_and_usable(self, tmp_path):
        """The one live step test: a genuine venv (no pip install)."""
        options = InstallOptions(
            install_dir=tmp_path / "install", python=sys.executable
        )
        log = InstallLog(tmp_path / "install.log", echo=lambda m: None)
        installer = Installer(
            options,
            registry=FakeRegistry(),
            log=log,
            desktop=tmp_path / "Desktop",
            start_menu=tmp_path / "StartMenu",
        )
        installer.create_venv()
        assert installer.venv_python.is_file()
        # Idempotent: a second run reuses it.
        installer.create_venv()

    def test_failed_venv_creation_raises(self, harness):
        harness.installer.venv_python.unlink()
        harness.runner.script("venv", returncode=1, stderr="disk full")
        with pytest.raises(InstallerError, match="venv creation failed"):
            harness.installer.create_venv()


class TestUninstall:
    def build(self, harness, keep_data=False):
        install_dir = harness.options.install_dir
        for name in ("config", "data", "logs", "backups"):
            (install_dir / name).mkdir(parents=True, exist_ok=True)
        (install_dir / "data" / "events.json").write_text("[]")
        (install_dir / "PAIOS.exe").write_bytes(b"exe")
        desktop = harness.tmp / "Desktop"
        desktop.mkdir(exist_ok=True)
        (desktop / SHORTCUT_NAME).write_bytes(b"lnk")
        menu = harness.tmp / "StartMenu" / START_MENU_FOLDER
        menu.mkdir(parents=True, exist_ok=True)
        (menu / SHORTCUT_NAME).write_bytes(b"lnk")
        harness.registry.set_run_value(RUN_VALUE_NAME, "x")
        return Uninstaller(
            install_dir,
            keep_data=keep_data,
            runner=harness.runner,
            registry=harness.registry,
            log=InstallLog(
                harness.tmp / "uninstall.log", echo=lambda m: None
            ),
            desktop=desktop,
            start_menu=harness.tmp / "StartMenu",
        )

    def test_full_uninstall_removes_everything(self, harness):
        uninstaller = self.build(harness)
        uninstaller.run()
        assert not harness.options.install_dir.exists()
        assert harness.registry.get_run_value(RUN_VALUE_NAME) is None
        assert not (harness.tmp / "Desktop" / SHORTCUT_NAME).exists()
        assert not (
            harness.tmp / "StartMenu" / START_MENU_FOLDER
        ).exists()
        assert any(
            command[0] == "schtasks" and "/Delete" in command
            for command in harness.runner.commands()
        )

    def test_keep_data_preserves_store_and_backups(self, harness):
        uninstaller = self.build(harness, keep_data=True)
        uninstaller.run()
        install_dir = harness.options.install_dir
        assert (install_dir / "data" / "events.json").is_file()
        assert (install_dir / "backups").is_dir()
        assert not (install_dir / "config").exists()
        assert not (install_dir / "PAIOS.exe").exists()
