"""Installer generation: the build pipeline that produces PAIOS.exe
and PAIOSSetup.exe. Command construction and payload staging are pure
and tested directly; the PyInstaller invocations themselves need the
build tool and are exercised by scripts/build_installer.py runs."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import build_installer  # noqa: E402


class TestCommandConstruction:
    def test_wheel_command_builds_the_repo_without_deps(self, tmp_path):
        command = build_installer.wheel_command(tmp_path)
        assert "wheel" in command
        assert "--no-deps" in command
        assert str(build_installer.REPO_ROOT) in command

    def test_launcher_is_onefile_windowed_named_paios(self, tmp_path):
        command = build_installer.launcher_command(
            tmp_path / "dist", tmp_path / "work"
        )
        assert "--onefile" in command
        assert "--windowed" in command
        assert command[command.index("--name") + 1] == "PAIOS"
        assert command[-1].endswith("__main__.py")
        assert "paios_launcher" in command[-1]
        # All three package roots are importable during analysis.
        paths = [
            command[i + 1]
            for i, part in enumerate(command)
            if part == "--paths"
        ]
        assert any("backend" in p for p in paths)
        assert any("desktop" in p for p in paths)
        assert any("launcher" in p for p in paths)

    def test_setup_is_console_named_paiossetup_with_payload(self, tmp_path):
        command = build_installer.setup_command(
            tmp_path / "dist", tmp_path / "work", tmp_path / "payload"
        )
        assert "--console" in command
        assert command[command.index("--name") + 1] == "PAIOSSetup"
        add_data = command[command.index("--add-data") + 1]
        assert add_data.endswith(
            f"{build_installer.ADD_DATA_SEPARATOR}payload"
        )
        assert "paios_installer" in command[-1]


class TestPayloadStaging:
    def test_stages_newest_wheel_and_launcher(self, tmp_path):
        wheels = tmp_path / "wheels"
        wheels.mkdir()
        (wheels / "paios-1.6.0-py3-none-any.whl").write_bytes(b"old")
        (wheels / "paios-1.7.0-py3-none-any.whl").write_bytes(b"new")
        launcher = tmp_path / "PAIOS.exe"
        launcher.write_bytes(b"exe")
        payload = tmp_path / "payload"
        staged = build_installer.stage_payload(payload, wheels, launcher)
        names = sorted(path.name for path in staged)
        assert names == ["PAIOS.exe", "paios-1.7.0-py3-none-any.whl"]
        assert (payload / "paios-1.7.0-py3-none-any.whl").read_bytes() == (
            b"new"
        )

    def test_missing_wheel_is_an_error(self, tmp_path):
        empty = tmp_path / "wheels"
        empty.mkdir()
        with pytest.raises(FileNotFoundError):
            build_installer.stage_payload(
                tmp_path / "payload", empty, None
            )

    def test_restaging_replaces_the_payload(self, tmp_path):
        wheels = tmp_path / "wheels"
        wheels.mkdir()
        (wheels / "paios-1.7.0-py3-none-any.whl").write_bytes(b"w")
        payload = tmp_path / "payload"
        payload.mkdir()
        (payload / "stale-file").write_bytes(b"stale")
        build_installer.stage_payload(payload, wheels, None)
        assert not (payload / "stale-file").exists()

    def test_launcher_is_optional(self, tmp_path):
        wheels = tmp_path / "wheels"
        wheels.mkdir()
        (wheels / "paios-1.7.0-py3-none-any.whl").write_bytes(b"w")
        staged = build_installer.stage_payload(
            tmp_path / "payload", wheels, None
        )
        assert [path.name for path in staged] == [
            "paios-1.7.0-py3-none-any.whl"
        ]


class TestReleaseArtifacts:
    """M20 release hygiene: what the GitHub Release must carry."""

    def test_updater_is_onefile_console_named_paiosupdater(self, tmp_path):
        command = build_installer.updater_command(
            tmp_path / "dist", tmp_path / "work"
        )
        assert "--onefile" in command
        assert "--console" in command
        assert command[command.index("--name") + 1] == "PAIOSUpdater"
        assert "paios_updater" in command[-1]

    def test_project_version_reads_pyproject(self):
        version = build_installer.project_version()
        assert version == "2.2.0"

    def test_checksums_file_in_sha256sum_format(self, tmp_path):
        artifact = tmp_path / "PAIOSSetup.exe"
        artifact.write_bytes(b"payload")
        missing = tmp_path / "not-built.exe"
        checksums = build_installer.write_checksums(
            tmp_path, [artifact, missing]
        )
        lines = checksums.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1  # missing files are skipped, not invented
        digest, name = lines[0].split()
        assert name == "PAIOSSetup.exe"
        assert digest == build_installer.sha256_of(artifact)

    def test_release_notes_extracts_current_changelog_section(
        self, tmp_path
    ):
        notes = build_installer.extract_release_notes("2.2.0")
        assert notes.startswith("## [2.2.0]")
        assert "## [2.1.0]" not in notes

    def test_release_notes_fall_back_for_unknown_version(self):
        assert build_installer.extract_release_notes("0.0.99") == (
            "PAIOS 0.0.99"
        )
