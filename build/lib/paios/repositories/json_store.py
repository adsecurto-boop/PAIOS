"""JSON file storage engine.

One JSON array file per aggregate inside the data folder
(ENTITY_RELATIONSHIPS.md - Local Data Storage: `.data/`). Writes are atomic:
content is written to a temporary sibling file and moved into place, so a
crash mid-write can never corrupt an existing file.
"""

import json
from pathlib import Path

from paios.repositories.errors import SerializationError


class JsonStore:
    """Reads and writes JSON array files inside a single data directory."""

    def __init__(self, data_dir: Path | str = ".data") -> None:
        self._data_dir = Path(data_dir)

    @property
    def data_dir(self) -> Path:
        return self._data_dir

    def initialize(self) -> None:
        """Create the data directory if it does not exist."""
        self._data_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, filename: str) -> Path:
        return self._data_dir / filename

    def read(self, filename: str) -> list[dict]:
        """Read all records from one aggregate file.

        A missing file and an empty file both mean "no records yet" — the
        store treats them as an empty collection rather than an error.
        """
        path = self.path_for(filename)
        if not path.exists():
            return []
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            return []
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SerializationError(
                f"{filename} contains corrupted JSON: {exc}"
            ) from exc
        if not isinstance(data, list):
            raise SerializationError(
                f"{filename} must contain a JSON array of records, "
                f"found {type(data).__name__}"
            )
        return data

    def write(self, filename: str, records: list[dict]) -> None:
        """Atomically replace one aggregate file with the given records."""
        self.initialize()
        path = self.path_for(filename)
        try:
            payload = json.dumps(records, indent=2, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise SerializationError(
                f"Records for {filename} are not JSON-serializable: {exc}"
            ) from exc
        temp_path = path.with_name(path.name + ".tmp")
        temp_path.write_text(payload, encoding="utf-8")
        temp_path.replace(path)
