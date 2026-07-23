"""Backups: zip archives of the JSON store. File operations only —
the domain remains untouched; restore/import happen against a stopped
application (the CLI enforces that by running before start).

Archive name: paios-backup-YYYYMMDD-HHMMSS.zip, containing the data
directory's *.json files at the archive root.
"""

import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

ARCHIVE_PREFIX = "paios-backup-"


@dataclass(frozen=True)
class BackupPolicy:
    enabled: bool = True
    interval_hours: float = 24.0
    keep: int = 14


class BackupError(Exception):
    pass


class BackupManager:
    def __init__(
        self,
        data_dir: str | Path,
        backup_dir: str | Path,
        policy: BackupPolicy | None = None,
    ) -> None:
        self._data_dir = Path(data_dir)
        self._backup_dir = Path(backup_dir)
        self.policy = policy if policy is not None else BackupPolicy()

    # --- create / prune ----------------------------------------------------

    def create(self, now: datetime | None = None) -> Path:
        """Zip every store file; prune to the keep limit; return the path."""
        stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        target = self._backup_dir / f"{ARCHIVE_PREFIX}{stamp}.zip"
        counter = 0
        while target.exists():  # same-second collisions (tests, scripts)
            counter += 1
            target = self._backup_dir / f"{ARCHIVE_PREFIX}{stamp}-{counter}.zip"
        self._write_archive(target)
        self._prune()
        return target

    def _write_archive(self, target: Path) -> None:
        files = self._store_files()
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in files:
                archive.write(path, arcname=path.name)

    def _store_files(self) -> list[Path]:
        if not self._data_dir.is_dir():
            raise BackupError(f"Data directory not found: {self._data_dir}")
        return sorted(self._data_dir.glob("*.json"))

    def _prune(self) -> None:
        backups = self.list_backups()
        for stale in backups[max(1, self.policy.keep):]:
            stale.unlink()

    def list_backups(self) -> list[Path]:
        """Newest first, by name (names embed the timestamp)."""
        if not self._backup_dir.is_dir():
            return []
        return sorted(
            self._backup_dir.glob(f"{ARCHIVE_PREFIX}*.zip"), reverse=True
        )

    # --- automatic policy ---------------------------------------------------

    def maybe_backup(self, now: datetime | None = None) -> Path | None:
        """Create a backup if the policy says one is due; else None."""
        if not self.policy.enabled:
            return None
        moment = now or datetime.now()
        newest = next(iter(self.list_backups()), None)
        if newest is not None:
            taken_at = _archive_moment(newest)
            if taken_at is not None:
                age = moment - taken_at
                if age < timedelta(hours=self.policy.interval_hours):
                    return None
        return self.create(moment)

    # --- restore / export / import -----------------------------------------

    def restore(self, archive: str | Path) -> list[str]:
        """Replace the data directory's store files with the archive's.
        Returns the restored file names."""
        path = self._locate(archive)
        names = _validated_names(path)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        for stale in self._store_files() if self._data_dir.is_dir() else []:
            stale.unlink()
        with zipfile.ZipFile(path) as source:
            source.extractall(self._data_dir)
        return names

    def export_to(self, destination: str | Path) -> Path:
        """A backup archive at an explicit location (share/move it)."""
        target = Path(destination)
        if target.is_dir():
            raise BackupError(f"Export target is a directory: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        self._write_archive(target)
        return target

    def import_from(self, source: str | Path) -> list[str]:
        """Restore from an arbitrary archive path (same validation)."""
        return self.restore(source)

    def _locate(self, archive: str | Path) -> Path:
        path = Path(archive)
        if path.is_file():
            return path
        candidate = self._backup_dir / str(archive)
        if candidate.is_file():
            return candidate
        raise BackupError(f"Backup archive not found: {archive}")


def _archive_moment(path: Path) -> datetime | None:
    """The timestamp embedded in the archive name (clock-independent —
    works with injected test clocks; None for foreign names)."""
    stem = path.stem[len(ARCHIVE_PREFIX):]
    try:
        return datetime.strptime(stem[:15], "%Y%m%d-%H%M%S")
    except ValueError:
        return None


def _validated_names(path: Path) -> list[str]:
    """The archive must be flat *.json members (defence against zip
    path tricks and wrong files)."""
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
    except zipfile.BadZipFile as error:
        raise BackupError(f"Not a PAIOS backup archive: {path}") from error
    if not names:
        raise BackupError(f"Archive is empty: {path}")
    for name in names:
        if "/" in name or "\\" in name or not name.endswith(".json"):
            raise BackupError(
                f"Archive member {name!r} is not a flat store file"
            )
    return names
