"""Backups: create, prune, policy, restore, export, import, safety."""

import zipfile
from datetime import datetime, timedelta

import pytest

from paios.system.backup import (
    BackupError,
    BackupManager,
    BackupPolicy,
)

T0 = datetime(2026, 7, 22, 9, 0, 0)


@pytest.fixture
def store(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "events.json").write_text('{"events": []}', encoding="utf-8")
    (data / "goals.json").write_text('{"goals": [1]}', encoding="utf-8")
    return data


@pytest.fixture
def manager(store, tmp_path):
    return BackupManager(store, tmp_path / "backups")


class TestCreate:
    def test_creates_archive_with_store_files(self, manager, store):
        archive = manager.create(T0)
        assert archive.name == "paios-backup-20260722-090000.zip"
        with zipfile.ZipFile(archive) as z:
            assert sorted(z.namelist()) == ["events.json", "goals.json"]

    def test_same_second_collision_gets_suffix(self, manager):
        first = manager.create(T0)
        second = manager.create(T0)
        assert first != second
        assert second.name.endswith("-1.zip")

    def test_prunes_to_keep_limit(self, store, tmp_path):
        manager = BackupManager(
            store, tmp_path / "backups", BackupPolicy(keep=2)
        )
        for minute in range(4):
            manager.create(T0 + timedelta(minutes=minute))
        remaining = manager.list_backups()
        assert len(remaining) == 2
        assert remaining[0].name == "paios-backup-20260722-090300.zip"

    def test_missing_data_dir_is_an_error(self, tmp_path):
        manager = BackupManager(tmp_path / "absent", tmp_path / "backups")
        with pytest.raises(BackupError, match="Data directory"):
            manager.create(T0)


class TestPolicy:
    def test_maybe_backup_respects_interval(self, manager):
        assert manager.maybe_backup(T0) is not None  # no backups yet -> due
        assert manager.maybe_backup(T0 + timedelta(hours=1)) is None
        assert (
            manager.maybe_backup(T0 + timedelta(hours=25)) is not None
        )

    def test_disabled_policy_never_backs_up(self, store, tmp_path):
        manager = BackupManager(
            store, tmp_path / "backups", BackupPolicy(enabled=False)
        )
        assert manager.maybe_backup(T0) is None
        assert manager.list_backups() == []


class TestRestoreExportImport:
    def test_restore_replaces_store(self, manager, store):
        archive = manager.create(T0)
        (store / "goals.json").write_text('{"goals": []}', encoding="utf-8")
        (store / "extra.json").write_text("{}", encoding="utf-8")
        names = manager.restore(archive.name)  # by name, not path
        assert sorted(names) == ["events.json", "goals.json"]
        assert (store / "goals.json").read_text(encoding="utf-8") == (
            '{"goals": [1]}'
        )
        assert not (store / "extra.json").exists()  # replaced, not merged

    def test_export_and_import_round_trip(self, manager, store, tmp_path):
        target = manager.export_to(tmp_path / "out" / "export.zip")
        (store / "goals.json").unlink()
        names = manager.import_from(target)
        assert "goals.json" in names
        assert (store / "goals.json").is_file()

    def test_unknown_archive_is_an_error(self, manager):
        with pytest.raises(BackupError, match="not found"):
            manager.restore("nope.zip")

    def test_rejects_non_backup_archives(self, manager, tmp_path):
        evil = tmp_path / "evil.zip"
        with zipfile.ZipFile(evil, "w") as z:
            z.writestr("nested/dir.json", "{}")
        with pytest.raises(BackupError, match="flat store file"):
            manager.import_from(evil)
        not_zip = tmp_path / "not.zip"
        not_zip.write_text("hello", encoding="utf-8")
        with pytest.raises(BackupError, match="Not a PAIOS backup"):
            manager.import_from(not_zip)
