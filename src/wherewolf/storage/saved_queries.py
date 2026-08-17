"""Persistent named-query storage independent from the Qt desktop application."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class SavedQuery:
    """A named SQL query that can be reused independently of execution history."""

    id: str
    name: str
    description: str
    sql: str
    created_at: str
    updated_at: str


class SavedQueryStore:
    """Store versioned saved-query records with atomic replacement writes."""

    DEFAULT_PATH = Path.home() / ".wherewolf" / "saved_queries.json"
    VERSION = 1

    def __init__(self, storage_path: Path | None = None) -> None:
        self.storage_path = storage_path or self.DEFAULT_PATH
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            self._write_queries(())

    def _write_queries(self, queries: tuple[SavedQuery, ...]) -> None:
        payload = {
            "version": self.VERSION,
            "queries": [
                {
                    "id": query.id,
                    "name": query.name,
                    "description": query.description,
                    "sql": query.sql,
                    "created_at": query.created_at,
                    "updated_at": query.updated_at,
                }
                for query in queries
            ],
        }
        temp_fd, temp_path = tempfile.mkstemp(dir=self.storage_path.parent, text=True)
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as file:
                json.dump(payload, file, indent=2)
            os.replace(temp_path, self.storage_path)
        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise

    def save_query(self, *, name: str, description: str, sql: str) -> SavedQuery:
        """Persist a new named query, rejecting names that already exist."""
        normalised_name = self._validate_name(name)
        self._validate_sql(sql)
        queries = self.get_all()
        self._ensure_name_available(normalised_name, queries)
        now = datetime.now(UTC).isoformat()
        query = SavedQuery(
            id=str(uuid4()),
            name=normalised_name,
            description=description,
            sql=sql,
            created_at=now,
            updated_at=now,
        )
        self._write_queries((*queries, query))
        return query

    def update_query(
        self,
        query_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        sql: str | None = None,
    ) -> SavedQuery | None:
        """Update one saved query and return it, or ``None`` when it is absent."""
        queries = self.get_all()
        current = self.get_by_id(query_id)
        if current is None:
            return None

        updated_name = self._validate_name(name) if name is not None else current.name
        if name is not None:
            self._ensure_name_available(updated_name, queries, excluding_id=query_id)
        updated_sql = sql if sql is not None else current.sql
        self._validate_sql(updated_sql)
        updated = replace(
            current,
            name=updated_name,
            description=description if description is not None else current.description,
            sql=updated_sql,
            updated_at=datetime.now(UTC).isoformat(),
        )
        self._write_queries(tuple(updated if query.id == query_id else query for query in queries))
        return updated

    def delete_query(self, query_id: str) -> bool:
        """Delete the named query identified by ``query_id`` if it exists."""
        queries = self.get_all()
        survivors = tuple(query for query in queries if query.id != query_id)
        if len(survivors) == len(queries):
            return False
        self._write_queries(survivors)
        return True

    def get_all(self) -> tuple[SavedQuery, ...]:
        """Load readable query records, skipping malformed siblings."""
        try:
            with self.storage_path.open(encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, json.JSONDecodeError):
            return ()

        if isinstance(payload, dict) and payload.get("version") == self.VERSION:
            raw_queries = payload.get("queries")
        elif isinstance(payload, list):
            # Legacy bare lists are the migration input for the versioned wrapper.
            raw_queries = payload
        else:
            return ()
        if not isinstance(raw_queries, list):
            return ()
        return tuple(
            query for raw_query in raw_queries if (query := self._load_query(raw_query)) is not None
        )

    def get_by_id(self, query_id: str) -> SavedQuery | None:
        """Return one saved query by its stable identifier."""
        return next((query for query in self.get_all() if query.id == query_id), None)

    @staticmethod
    def _load_query(raw_query: object) -> SavedQuery | None:
        if not isinstance(raw_query, dict):
            return None
        query_id = raw_query.get("id")
        name = raw_query.get("name")
        description = raw_query.get("description")
        sql = raw_query.get("sql")
        created_at = raw_query.get("created_at")
        updated_at = raw_query.get("updated_at")
        if (
            not isinstance(query_id, str)
            or not isinstance(name, str)
            or not isinstance(description, str)
            or not isinstance(sql, str)
            or not isinstance(created_at, str)
            or not isinstance(updated_at, str)
        ):
            return None
        try:
            UUID(query_id)
        except ValueError:
            return None
        return SavedQuery(
            id=query_id,
            name=name,
            description=description,
            sql=sql,
            created_at=created_at,
            updated_at=updated_at,
        )

    @staticmethod
    def _validate_name(name: str) -> str:
        normalised_name = name.strip()
        if not normalised_name:
            raise ValueError("Saved query name cannot be empty")
        return normalised_name

    @staticmethod
    def _validate_sql(sql: str) -> None:
        if not sql.strip():
            raise ValueError("Saved query SQL cannot be empty")

    @staticmethod
    def _ensure_name_available(
        name: str,
        queries: tuple[SavedQuery, ...],
        *,
        excluding_id: str | None = None,
    ) -> None:
        if any(
            query.id != excluding_id and query.name.casefold() == name.casefold()
            for query in queries
        ):
            raise ValueError(f"A saved query named {name!r} already exists")


__all__ = ["SavedQuery", "SavedQueryStore"]
