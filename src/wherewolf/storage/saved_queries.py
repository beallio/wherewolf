"""Directory-backed saved-query library independent from the Qt desktop application."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from wherewolf.services.export_destination import write_atomically

SQL_SUFFIX = ".sql"


@dataclass(frozen=True, slots=True)
class SavedQuery:
    """One ``.sql`` file in the configured library directory."""

    id: str
    name: str
    description: str
    sql: str
    updated_at: str


def extract_description(sql: str) -> str:
    """Return the leading comment of a query with its comment markers removed."""
    lines = sql.splitlines()
    index = 0
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines):
        return ""

    first = lines[index].strip()
    if first.startswith("--"):
        collected = []
        while index < len(lines) and lines[index].strip().startswith("--"):
            collected.append(lines[index].strip().removeprefix("--").strip())
            index += 1
        return "\n".join(collected).strip()
    if first.startswith("/*"):
        collected = []
        while index < len(lines):
            line = lines[index].strip()
            terminated = line.endswith("*/")
            collected.append(line.removeprefix("/*").removesuffix("*/").strip())
            index += 1
            if terminated:
                break
        return "\n".join(part for part in collected if part).strip()
    return ""


class SavedQueryDirectory:
    """Expose the ``.sql`` files under one directory as named saved queries."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    @property
    def directory(self) -> Path:
        return self._directory

    def set_directory(self, directory: Path) -> None:
        """Point the library at another directory without rebuilding consumers."""
        self._directory = directory

    def get_all(self) -> tuple[SavedQuery, ...]:
        """Load every readable ``*.sql`` file below the directory, sorted by name."""
        root = self._directory
        try:
            candidates = sorted(
                (path for path in root.rglob("*") if self._is_query_file(path, root)),
                key=lambda path: str(path.relative_to(root)).casefold(),
            )
        except OSError:
            return ()

        queries = []
        for path in candidates:
            query = self._load_query(path, root)
            if query is not None:
                queries.append(query)
        return tuple(queries)

    def save_query(self, *, name: str, sql: str) -> SavedQuery:
        """Write a new query file, rejecting a name that is already taken."""
        destination = self._resolve_name(name)
        self._ensure_available(destination)
        self._write(destination, sql)
        return self._require_query(destination)

    def rename_query(self, query_id: str, name: str) -> SavedQuery | None:
        """Move one query file and return it, or ``None`` when it is absent."""
        source = Path(query_id)
        if not source.is_file():
            return None
        destination = self._resolve_name(name)
        if destination != source:
            self._ensure_available(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            source.rename(destination)
        return self._require_query(destination)

    def delete_query(self, query_id: str) -> bool:
        """Delete one query file if it is still present."""
        try:
            Path(query_id).unlink()
        except (FileNotFoundError, IsADirectoryError):
            return False
        return True

    @staticmethod
    def _is_query_file(path: Path, root: Path) -> bool:
        if path.suffix.casefold() != SQL_SUFFIX:
            return False
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            return False
        return path.is_file()

    @staticmethod
    def _load_query(path: Path, root: Path) -> SavedQuery | None:
        try:
            sql = path.read_text(encoding="utf-8")
            modified_at = path.stat().st_mtime
        except (OSError, UnicodeDecodeError):
            return None
        relative = PurePosixPath(*path.relative_to(root).parts)
        return SavedQuery(
            id=str(path),
            name=str(relative.with_suffix("")),
            description=extract_description(sql),
            sql=sql,
            updated_at=datetime.fromtimestamp(modified_at, UTC).isoformat(),
        )

    def _require_query(self, path: Path) -> SavedQuery:
        query = self._load_query(path, self._directory)
        if query is None:
            raise OSError(f"Could not read the saved query at {path}")
        return query

    def _resolve_name(self, name: str) -> Path:
        """Map a relative library name onto a path inside the directory."""
        normalised = name.strip()
        if not normalised:
            raise ValueError("Saved query name cannot be empty")
        if "\\" in normalised or "\x00" in normalised:
            raise ValueError("Saved query name cannot contain backslashes")
        parts = normalised.split("/")
        if any(not part or part in {".", ".."} for part in parts):
            raise ValueError(f"{name!r} is not a usable saved query name")
        if any(part != part.rstrip(" .") for part in parts):
            raise ValueError("Saved query name parts cannot end with a space or a dot")

        root = self._directory
        destination = root.joinpath(*parts).with_suffix(SQL_SUFFIX)
        if not self._is_inside(destination, root):
            raise ValueError(f"{name!r} resolves outside the saved query folder")
        return destination

    @staticmethod
    def _is_inside(destination: Path, root: Path) -> bool:
        try:
            return os.path.abspath(destination).startswith(f"{os.path.abspath(root)}{os.sep}")
        except OSError:
            return False

    @staticmethod
    def _ensure_available(destination: Path) -> None:
        if destination.exists():
            raise ValueError(f"A saved query named {destination.stem!r} already exists")

    @staticmethod
    def _write(destination: Path, sql: str) -> None:
        def write(path: Path) -> None:
            path.write_text(sql, encoding="utf-8")

        write_atomically(destination, write)


__all__ = ["SQL_SUFFIX", "SavedQuery", "SavedQueryDirectory", "extract_description"]
