"""Persistent catalog storage independent from the Qt desktop application."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from uuid import UUID

from wherewolf.domain import CatalogEntry, SourceFormat


class CatalogStore:
    """Store the minimal catalog projection needed to restore dataset entries."""

    DEFAULT_PATH = Path.home() / ".wherewolf" / "catalog.json"

    def __init__(self, storage_path: Path | None = None) -> None:
        self.storage_path = storage_path or self.DEFAULT_PATH
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            self.storage_path.write_text("[]")

    def save(self, entries: tuple[CatalogEntry, ...]) -> None:
        """Atomically write only fields needed to recreate catalog entries."""
        persisted_entries = [
            {
                "id": str(entry.id),
                "alias": entry.alias,
                "path": str(entry.path),
                "source_format": entry.source_format.value,
            }
            for entry in entries
        ]
        self._write_catalog({"version": 1, "entries": persisted_entries})

    def _write_catalog(self, catalog: dict[str, object]) -> None:
        temp_fd, temp_path = tempfile.mkstemp(dir=self.storage_path.parent, text=True)
        try:
            with os.fdopen(temp_fd, "w") as file:
                json.dump(catalog, file, indent=2)
            os.replace(temp_path, self.storage_path)
        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise

    def load(self) -> tuple[CatalogEntry, ...]:
        """Load all readable entries, skipping malformed records independently."""
        try:
            with self.storage_path.open() as file:
                raw_catalog = json.load(file)
        except (OSError, json.JSONDecodeError):
            return ()

        if isinstance(raw_catalog, list):
            raw_entries = raw_catalog
        elif isinstance(raw_catalog, dict) and raw_catalog.get("version") == 1:
            raw_entries = raw_catalog.get("entries")
        else:
            return ()

        if not isinstance(raw_entries, list):
            return ()

        return tuple(entry for raw_entry in raw_entries if (entry := self._load_entry(raw_entry)))

    @staticmethod
    def _load_entry(raw_entry: object) -> CatalogEntry | None:
        if not isinstance(raw_entry, dict):
            return None

        entry_id = raw_entry.get("id")
        alias = raw_entry.get("alias")
        path = raw_entry.get("path")
        source_format = raw_entry.get("source_format")
        if (
            not isinstance(entry_id, str)
            or not entry_id
            or not isinstance(alias, str)
            or not alias
            or not isinstance(path, str)
            or not path
            or not isinstance(source_format, str)
            or not source_format
        ):
            return None

        try:
            return CatalogEntry(
                id=UUID(entry_id),
                alias=alias,
                path=Path(path),
                source_format=SourceFormat(source_format),
            )
        except ValueError:
            return None


__all__ = ["CatalogStore"]
