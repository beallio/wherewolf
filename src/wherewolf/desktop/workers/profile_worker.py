"""Dataset profiling worker for catalog entries."""

from __future__ import annotations

import uuid
from typing import Protocol

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from wherewolf.domain import CatalogBinding, CatalogEntry, ProfileResult
from wherewolf.domain.enums import EngineKind


class ProfileEngineAdapter(Protocol):
    def profile_dataset(self, entry: CatalogEntry) -> ProfileResult: ...
    def close(self) -> None: ...


class ProfileEngineRegistry(Protocol):
    def create(self, kind: EngineKind, request_id: uuid.UUID) -> ProfileEngineAdapter: ...


class ProfileWorker(QThread):
    """Run full-scan dataset profiling off the GUI thread."""

    result_ready = pyqtSignal(ProfileResult)

    def __init__(
        self,
        engine_registry: ProfileEngineRegistry,
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
            self.result_ready.emit(adapter.profile_dataset(entry))
        except Exception as exc:  # noqa: BLE001
            self.result_ready.emit(
                ProfileResult(
                    entry_id=self._binding.entry_id,
                    profiles=None,
                    error_type="profile_worker_failed",
                    error_message=str(exc),
                )
            )
        finally:
            if adapter is not None:
                try:
                    adapter.close()
                except Exception:  # noqa: BLE001, S110  # Cleanup is best effort.
                    pass


__all__ = ["ProfileWorker"]
