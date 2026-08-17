import json
import os
import tempfile
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4


class HistoryManager:
    """Manages local query history persistence."""

    DEFAULT_PATH = Path.home() / ".wherewolf" / "history.json"

    def __init__(self, storage_path: Path | None = None):
        self.storage_path = storage_path or self.DEFAULT_PATH
        self._ensure_storage()

    def _ensure_storage(self):
        """Ensures the storage directory exists."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            with open(self.storage_path, "w") as f:
                json.dump([], f)

    def _write_history(self, history: list[dict]) -> None:
        """Atomically persist the complete history without replacing a good file on failure."""
        temp_fd, temp_path = tempfile.mkstemp(dir=self.storage_path.parent, text=True)
        try:
            with os.fdopen(temp_fd, "w") as f:
                json.dump(history, f, indent=2)
            os.replace(temp_path, self.storage_path)
        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise

    @staticmethod
    def _migrate_v1_entry(entry: dict) -> dict:
        """Return the v2 representation of one legacy history entry."""
        migrated = dict(entry)
        migrated["schema_version"] = 2
        migrated["id"] = str(uuid4())
        migrated.setdefault("catalog", {"dataset": migrated.get("path", "")})
        migrated["pinned"] = False
        return migrated

    @staticmethod
    def _has_required_keys(entry: dict) -> bool:
        return all(
            isinstance(entry.get(key), str) and entry[key]
            for key in ("timestamp", "engine", "query")
        )

    @classmethod
    def _is_v2_entry(cls, entry: object) -> bool:
        if not isinstance(entry, dict) or entry.get("schema_version") != 2:
            return False
        entry_id = entry.get("id")
        pinned = entry.get("pinned", False)
        if (
            not cls._has_required_keys(entry)
            or not isinstance(entry_id, str)
            or not isinstance(pinned, bool)
        ):
            return False
        try:
            UUID(entry_id)
        except ValueError:
            return False
        return True

    @classmethod
    def _is_v1_entry(cls, entry: object) -> bool:
        return (
            isinstance(entry, dict)
            and "schema_version" not in entry
            and "id" not in entry
            and cls._has_required_keys(entry)
        )

    def add_entry(
        self, engine: str, query: str, path: str = "", catalog: dict[str, str] | None = None
    ):
        """Adds a new query to the history.

        Args:
            engine: The execution engine used (e.g., 'duckdb').
            query: The SQL query string.
            path: The dataset path used (legacy).
            catalog: A mapping of aliases to filesystem paths.
        """
        history = self.get_all()
        entry = {
            "schema_version": 2,
            "id": str(uuid4()),
            # Local time with an explicit UTC offset. `astimezone()` keeps the
            # first 16 characters identical to the previous naive local format,
            # which app.py slices for history labels, while making the value
            # unambiguous for the schema-v2 migration.
            "timestamp": datetime.now().astimezone().isoformat(),
            "engine": engine,
            "query": query,
            "path": path,
            "catalog": catalog if catalog is not None else {"dataset": path} if path else {},
            "pinned": False,
        }
        history.insert(0, entry)  # Add to the beginning

        # Pinned queries are user-curated and intentionally exempt from the ordinary
        # history cap. Keep every pinned record and the 100 newest unpinned records.
        pinned_entries = [entry for entry in history if entry["pinned"]]
        unpinned_entries = [entry for entry in history if not entry["pinned"]]
        history = [*pinned_entries, *unpinned_entries[:100]]

        self._write_history(history)

    def get_all(self) -> list[dict]:
        """Returns all history entries.

        Returns:
            A list of history entry dictionaries.
        """
        try:
            if not self.storage_path.exists():
                return []
            with open(self.storage_path, "r") as f:
                history = json.load(f)
        except (OSError, json.JSONDecodeError):
            return []

        if not isinstance(history, list):
            return []

        readable_entries: list[dict] = []
        migrated = False
        for entry in history:
            if self._is_v2_entry(entry):
                normalised_entry = dict(entry)
                if "pinned" not in normalised_entry:
                    normalised_entry["pinned"] = False
                    migrated = True
                readable_entries.append(normalised_entry)
            elif self._is_v1_entry(entry):
                readable_entries.append(self._migrate_v1_entry(entry))
                migrated = True

        if migrated:
            self._write_history(readable_entries)
        return readable_entries

    def get_by_id(self, entry_id: str) -> dict | None:
        """Return the history record identified by its stable UUID, if present."""
        return next((entry for entry in self.get_all() if entry["id"] == entry_id), None)

    def delete_records(self, entry_ids: Iterable[str]) -> int:
        """Delete all records whose stable ids occur in ``entry_ids``."""
        ids_to_delete = set(entry_ids)
        if not ids_to_delete:
            return 0

        history = self.get_all()
        survivors = [entry for entry in history if entry["id"] not in ids_to_delete]
        removed_count = len(history) - len(survivors)
        if removed_count:
            self._write_history(survivors)
        return removed_count

    def set_pinned(self, entry_id: str, pinned: bool) -> None:
        """Persist the requested pin state for one history record."""
        history = self.get_all()
        for entry in history:
            if entry["id"] == entry_id:
                if entry["pinned"] != pinned:
                    entry["pinned"] = pinned
                    self._write_history(history)
                return

    def clear(self):
        """Clears the query history."""
        self._write_history([])
