"""Schema inspection worker for catalog entries."""

from __future__ import annotations

import uuid
from typing import Protocol

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from wherewolf.domain import CatalogBinding, CatalogEntry, SchemaResult
from wherewolf.domain.enums import EngineKind


class SchemaEngineAdapter(Protocol):
    def inspect_schema(self, entry: CatalogEntry) -> SchemaResult: ...
    def close(self) -> None: ...


class SchemaEngineRegistry(Protocol):
    def create(self, kind: EngineKind, request_id: uuid.UUID) -> SchemaEngineAdapter: ...


class SchemaWorker(QThread):
    """Run schema inspection off the GUI thread and emit a `SchemaResult`."""

    result_ready = pyqtSignal(SchemaResult)

    def __init__(
        self,
        engine_registry: SchemaEngineRegistry,
        binding: CatalogBinding,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._engine_registry = engine_registry
        self._binding = binding

    def run(self) -> None:  # pragma: no cover - exercised via Qt integration tests
        entry = CatalogEntry(
            id=self._binding.entry_id,
            alias=self._binding.alias,
            path=self._binding.path,
            source_format=self._binding.source_format,
        )

        adapter = None
        try:
            adapter = self._engine_registry.create(EngineKind.DUCKDB, uuid.uuid4())
            self.result_ready.emit(adapter.inspect_schema(entry))
        except Exception as exc:  # noqa: BLE001
            self.result_ready.emit(
                SchemaResult(
                    entry_id=self._binding.entry_id,
                    columns=None,
                    error_type="schema_worker_failed",
                    error_message=str(exc),
                )
            )
        finally:
            if adapter is not None:
                try:
                    adapter.close()
                except Exception:  # noqa: BLE001
                    # Engine adapter close is best effort; cleanup failures should not abort UI flow.
                    _ = True


__all__ = ["SchemaWorker"]
