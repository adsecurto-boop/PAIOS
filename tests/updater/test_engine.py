"""The update engine pipeline with fakes: no network, no real installs."""

import json
import zipfile
from pathlib import Path

import pytest

from paios_updater import checksums, releases
from paios_updater.engine import (
    UpdateEngine,
    UpdateError,
    UpdaterConfig,
)


def make_install(tmp_path: Path, version: str = "2.1.0") -> Path:
    install = tmp_path / "PAIOS"
    install.mkdir()
    (install / "PAIOS.exe").write_bytes(b"old-launcher")
    (install / "version.txt").write_text(version + "\n", encoding="utf-8")
    site = install / "venv" / "Lib" / "site-packages" / "paios"
    site.mkdir(parents=True)
    (site / "__init__.py").write_text(
        f'__version__ = "{version}"\n', encoding="utf-8"
    )
    return install


def release_feed(tag="v2.2.0"):
    def fetcher(url):
        return json.dumps(
            {
                "tag_name": tag,
                "body": "notes",
                "assets": [
                    {"name": releases.SETUP_ASSET,
                     "browser_download_url": "https://x/setup"},
                    {"name": releases.CHECKSUMS_ASSET,
                     "browser_download_url": "https://x/sums"},
                ],
            }
        )

    return fetcher


SETUP_BYTES = b"new-installer-bytes"


def fake_downloader(url: str, target: Path) -> None:
    if target.name == releases.SETUP_ASSET:
        target.write_bytes(SETUP_BYTES)
    else:
        import hashlib

        digest = hashlib.sha256(SETUP_BYTES).hexdigest()
        target.write_text(
            f"{digest}  {releases.SETUP_ASSET}\n", encoding="utf-8"
        )


class InstallingRunner:
    """Simulates PAIOSSetup.exe: bumps the install's version files."""

    def __init__(self, install: Path, to_version: str = "2.2.0",
                 exit_code: int = 0, corrupt: bool = False) -> None:
        self.install = install
        self.to_version = to_version
        self.exit_code = exit_code
        self.corrupt = corrupt
        self.commands = []

    def __call__(self, command, timeout):
        self.commands.append(tuple(command))
        if command[0].endswith(releases.SETUP_ASSET.replace(".exe", "")) or (
            command[0].endswith(releases.SETUP_ASSET)
        ):
            if self.exit_code == 0:
                new_version = (
                    "0.0.0-broken" if self.corrupt else self.to_version
                )
                (self.install / "version.txt").unlink(missing_ok=True)
                (self.install / "PAIOS.exe").write_bytes(b"new-launcher")
                package = (
                    self.install / "venv" / "Lib" / "site-packages" / "paios"
                )
                (package / "__init__.py").write_text(
                    f'__version__ = "{new_version}"\n', encoding="utf-8"
                )
            return self.exit_code
        return 0


@pytest.fixture
def engine_factory(tmp_path, monkeypatch):
    def build(runner=None, tag="v2.2.0", version="2.1.0"):
        install = make_install(tmp_path, version)
        runner = runner or InstallingRunner(install)

        engine = UpdateEngine(
            config=UpdaterConfig(install_dir=install),
            fetcher=release_feed(tag),
            downloader=fake_downloader,
            runner=runner,
            log=lambda message: None,
        )
        # The health check asks the venv python; fake it by reading the
        # package __init__ the fake installer writes.
        def fake_installed_version(self=engine):
            package_init = (
                install / "venv" / "Lib" / "site-packages" / "paios"
                / "__init__.py"
            )
            if engine.config.version_file.is_file():
                return engine.config.version_file.read_text(
                    encoding="utf-8"
                ).strip()
            text = package_init.read_text(encoding="utf-8")
            return text.split('"')[1]

        monkeypatch.setattr(
            UpdateEngine, "installed_version", fake_installed_version
        )
        return engine, install, runner

    return build


class TestCheck:
    def test_no_update_when_current(self, engine_factory):
        engine, _, _ = engine_factory(tag="v2.1.0")
        assert engine.check() is None

    def test_plan_produced_for_newer_release(self, engine_factory):
        engine, _, _ = engine_factory(tag="v2.2.0")
        plan = engine.check()
        assert plan is not None
        assert plan.current_version == "2.1.0"
        assert plan.target_version == "2.2.0"
        assert plan.notes == "notes"

    def test_release_without_assets_is_an_error(self, tmp_path):
        install = make_install(tmp_path)

        def bare_feed(url):
            return json.dumps({"tag_name": "v9.9.9", "assets": []})

        engine = UpdateEngine(
            config=UpdaterConfig(install_dir=install),
            fetcher=bare_feed,
            log=lambda message: None,
        )
        with pytest.raises(UpdateError, match="missing"):
            engine.check()


class TestApply:
    def test_successful_update_installs_and_restarts(
        self, engine_factory, monkeypatch
    ):
        engine, install, runner = engine_factory()
        restarts = []
        monkeypatch.setattr(
            UpdateEngine, "_restart_paios",
            lambda self: restarts.append(True),
        )
        plan = engine.check()
        engine.apply(plan)
        assert (install / "PAIOS.exe").read_bytes() == b"new-launcher"
        assert (install / "version.txt").read_text(
            encoding="utf-8"
        ).strip() == "2.2.0"
        assert restarts == [True]
        # Stop was requested before install, on the old launcher.
        assert any("--stop" in command for command in runner.commands)
        # A backup exists.
        backups = list((install / "backups" / "updates").glob("*.zip"))
        assert len(backups) == 1
        with zipfile.ZipFile(backups[0]) as archive:
            names = set(archive.namelist())
        assert "PAIOS.exe" in names
        assert "manifest.json" in names

    def test_failed_installer_rolls_back(self, engine_factory, monkeypatch):
        def build_failing(install):
            return InstallingRunner(install, exit_code=7)

        engine, install, _ = engine_factory(
            runner=None
        )
        # Replace runner with a failing one bound to the same install.
        engine.runner = InstallingRunner(install, exit_code=7)
        monkeypatch.setattr(
            UpdateEngine, "_restart_paios", lambda self: None
        )
        plan = engine.check()
        with pytest.raises(UpdateError) as failure:
            engine.apply(plan)
        assert failure.value.rolled_back is True
        assert (install / "PAIOS.exe").read_bytes() == b"old-launcher"

    def test_health_check_failure_rolls_back(
        self, engine_factory, monkeypatch
    ):
        engine, install, _ = engine_factory()
        engine.runner = InstallingRunner(install, corrupt=True)
        monkeypatch.setattr(
            UpdateEngine, "_restart_paios", lambda self: None
        )
        plan = engine.check()
        with pytest.raises(UpdateError) as failure:
            engine.apply(plan)
        assert failure.value.rolled_back is True
        assert (install / "PAIOS.exe").read_bytes() == b"old-launcher"

    def test_checksum_mismatch_aborts_before_any_change(
        self, engine_factory
    ):
        engine, install, runner = engine_factory()

        def tampering_downloader(url, target):
            if target.name == releases.SETUP_ASSET:
                target.write_bytes(b"tampered")
            else:
                fake_downloader(url, target)

        engine.downloader = tampering_downloader
        plan = engine.check()
        with pytest.raises(checksums.ChecksumError):
            engine.apply(plan)
        # Nothing was stopped, backed up, or replaced.
        assert (install / "PAIOS.exe").read_bytes() == b"old-launcher"
        assert not (install / "backups" / "updates").exists()
        assert not any("--stop" in command for command in runner.commands)
