"""Background worker for grouped value counts."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from wherewolf.domain import CatalogBinding, CatalogEntry
from wherewolf.domain.enums import EngineKind


@dataclass(frozen=True, slots=True)
class ValueCount:
    value: object
    count: int
    percentage: float


@dataclass(frozen=True, slots=True)
class ValueCountsResult:
    entry_id: uuid.UUID
    column_name: str
    counts: tuple[ValueCount, ...]
    total_distinct: int
    error_type: str | None = None
    error_message: str | None = None


class ValueCountsAdapter(Protocol):
    def value_counts(
        self, entry: object, column_name: str, limit: int
    ) -> tuple[tuple[tuple[object, int], ...], int, int]: ...

    def close(self) -> None: ...


class ValueCountsRegistry(Protocol):
    def create(self, kind: EngineKind, request_id: uuid.UUID) -> ValueCountsAdapter: ...


class ValueCountsWorker(QThread):
    """Run a bounded grouped-count query off the GUI thread."""

    result_ready = pyqtSignal(object)

    def __init__(
        self,
        engine_registry: ValueCountsRegistry,
        binding: CatalogBinding,
        column_name: str,
        limit: int,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._engine_registry = engine_registry
        self._binding = binding
        self._column_name = column_name
        self._limit = max(1, int(limit))

    def run(self) -> None:  # pragma: no cover - exercised via Qt integration tests
        adapter = None
        try:
            adapter = self._engine_registry.create(EngineKind.DUCKDB, uuid.uuid4())
            entry = CatalogEntry(
                id=self._binding.entry_id,
                alias=self._binding.alias,
                path=self._binding.path,
                source_format=self._binding.source_format,
            )
            raw_counts, total_distinct, total_rows = adapter.value_counts(
                entry, self._column_name, self._limit
            )
            denominator = max(0, total_rows)
            counts = tuple(
                ValueCount(
                    value=value,
                    count=int(count),
                    percentage=(float(count) / denominator * 100.0 if denominator else 0.0),
                )
                for value, count in raw_counts
            )
            self.result_ready.emit(
                ValueCountsResult(
                    entry_id=self._binding.entry_id,
                    column_name=self._column_name,
                    counts=counts,
                    total_distinct=int(total_distinct),
                )
            )
        except Exception as error:  # noqa: BLE001
            self.result_ready.emit(
                ValueCountsResult(
                    entry_id=self._binding.entry_id,
                    column_name=self._column_name,
                    counts=(),
                    total_distinct=0,
                    error_type=type(error).__name__,
                    error_message=str(error),
                )
            )
        finally:
            if adapter is not None:
                try:
                    adapter.close()
                except Exception:  # noqa: BLE001, S110
                    pass


__all__ = ["ValueCount", "ValueCountsResult", "ValueCountsWorker"]
