"""Dataset catalog domain logic for desktop UI."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final
from uuid import UUID, uuid4

from wherewolf.domain import CatalogBinding, CatalogEntry, ProfileResult, SchemaResult, SourceFormat
from wherewolf.domain.errors import UnsupportedFormatError


@dataclass(frozen=True, slots=True)
class CatalogServiceReport:
    added: tuple[CatalogEntry, ...]
    duplicates: tuple[Path, ...]
    warnings: tuple[str, ...]


class CatalogService:
    """Pure logic service for dataset catalog state.

    This service intentionally contains no Qt imports so it can be tested and
    reused independent of the UI stack.
    """

    _MAX_ALIAS_SUFFIX: Final = 99_999
    _ALIAS_VALID_PATTERN: Final = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

    def __init__(self, initial_entries: tuple[CatalogEntry, ...] | None = None) -> None:
        self._entries: tuple[CatalogEntry, ...] = initial_entries or ()
        self._listeners: tuple[Callable[[], None], ...] = ()

    @property
    def entries(self) -> tuple[CatalogEntry, ...]:
        return self._entries

    def subscribe(self, listener: Callable[[], None]) -> None:
        self._listeners = (*self._listeners, listener)

    def unsubscribe(self, listener: Callable[[], None]) -> None:
        self._listeners = tuple(
            existing for existing in self._listeners if existing is not listener
        )

    def add_paths(self, paths: tuple[Path, ...]) -> CatalogServiceReport:
        resolved_paths: list[Path] = [path.expanduser().resolve() for path in paths]
        existing_paths = {entry.path for entry in self._entries}
        used_aliases = {entry.alias.casefold() for entry in self._entries}

        added: list[CatalogEntry] = []
        duplicates: list[Path] = []
        warnings: list[str] = []

        for source_path in resolved_paths:
            try:
                source_format = SourceFormat.from_path(source_path)
            except UnsupportedFormatError as exc:
                warnings.append(f"Unsupported source format for {source_path}: {exc}")
                continue

            if source_path in existing_paths:
                duplicates.append(source_path)
                continue

            alias = self._to_alias(source_path.stem, used_aliases)
            used_aliases.add(alias.casefold())
            existing_paths.add(source_path)

            entry = CatalogEntry(
                id=uuid4(),
                alias=alias,
                path=source_path,
                source_format=source_format,
                schema=None,
                schema_error=None,
            )
            added.append(entry)
            existing_paths.add(source_path)

        if added:
            self._entries = (*self._entries, *added)
            self._notify()

        return CatalogServiceReport(
            added=tuple(added),
            duplicates=tuple(duplicates),
            warnings=tuple(warnings),
        )

    def rename(self, entry_id: UUID, alias: str) -> None:
        if not alias:
            raise ValueError("Invalid alias: alias cannot be empty")
        if not self._ALIAS_VALID_PATTERN.match(alias):
            raise ValueError("Invalid alias: must be a SQL identifier")

        normalized = alias.casefold()
        entries = list(self._entries)
        index = next((i for i, entry in enumerate(entries) if entry.id == entry_id), None)
        if index is None:
            raise KeyError(f"No catalog entry with id {entry_id}")

        for idx, existing in enumerate(entries):
            if existing.id != entry_id and existing.alias.casefold() == normalized:
                raise ValueError(f"Alias '{alias}' already exists")

        entry = entries[index]
        entries[index] = replace(entry, alias=alias)
        if entries != list(self._entries):
            self._entries = tuple(entries)
            self._notify()

    def remove(self, entry_id: UUID) -> bool:
        remaining = tuple(entry for entry in self._entries if entry.id != entry_id)
        if len(remaining) == len(self._entries):
            return False

        self._entries = remaining
        self._notify()
        return True

    def update_schema(self, schema_result: SchemaResult) -> None:
        if schema_result.columns is not None:
            updated_schema = schema_result.columns
            schema_error = None
        else:
            updated_schema = None
            schema_error = schema_result.error_message or "schema inspection failed"

        entries = list(self._entries)
        index = next(
            (i for i, entry in enumerate(entries) if entry.id == schema_result.entry_id), None
        )
        if index is None:
            return

        entry = entries[index]
        entries[index] = replace(
            entry,
            schema=updated_schema,
            schema_error=schema_error,
        )
        self._entries = tuple(entries)
        self._notify()

    def update_profile(self, profile_result: ProfileResult) -> None:
        index = next(
            (i for i, entry in enumerate(self._entries) if entry.id == profile_result.entry_id),
            None,
        )
        if index is None:
            return
        entries = list(self._entries)
        entry = entries[index]
        entries[index] = replace(
            entry,
            profile=profile_result.profiles,
            profile_error=profile_result.error_message,
            profile_stale=False,
            profile_skipped_reason=None,
        )
        self._entries = tuple(entries)
        self._notify()

    def mark_profile_skipped(self, entry_id: UUID, reason: str) -> None:
        self._entries = tuple(
            replace(entry, profile_skipped_reason=reason) if entry.id == entry_id else entry
            for entry in self._entries
        )
        self._notify()

    def snapshot(self) -> tuple[CatalogBinding, ...]:
        return tuple(
            CatalogBinding(
                entry_id=entry.id,
                alias=entry.alias,
                path=entry.path,
                source_format=entry.source_format,
            )
            for entry in self._entries
        )

    def _notify(self) -> None:
        for listener in self._listeners:
            listener()

    def _to_alias(self, name: str, used_aliases: set[str]) -> str:
        sanitized = re.sub(r"[^0-9A-Za-z_]", "_", name).strip("_")
        if not sanitized or sanitized[0].isdigit():
            sanitized = f"_{sanitized}"
        sanitized = re.sub(r"_+", "_", sanitized)

        base = sanitized.lower()
        candidate = base
        index = 2
        while candidate.casefold() in used_aliases:
            candidate = f"{base}_{index}"
            index += 1
            if index >= self._MAX_ALIAS_SUFFIX:
                raise ValueError("Cannot generate unique alias")
        return candidate


__all__ = ["CatalogService", "CatalogServiceReport"]
