"""Background execution worker for SQL requests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from wherewolf.domain import ExecutionRequest, ExecutionStatus, QueryResult
from wherewolf.domain.enums import EngineKind
from wherewolf.execution.base import ExecutionEngine


class ExecutionEngineRegistry(Protocol):
    def create(self, kind: EngineKind, request_id: object) -> ExecutionEngine: ...


class ExecutionWorker(QThread):
    """Run SQL query execution off the GUI thread and emit results."""

    handle_published = pyqtSignal(object)
    result_ready = pyqtSignal(object)

    def __init__(
        self,
        engine_registry: ExecutionEngineRegistry,
        request: ExecutionRequest,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._engine_registry = engine_registry
        self._request = request

    def run(self) -> None:  # pragma: no cover - exercised via Qt integration tests
        adapter: ExecutionEngine | None = None
        try:
            adapter = self._engine_registry.create(self._request.engine, self._request.request_id)
            handle = adapter.cancellation_handle()
            self.handle_published.emit(handle)

            result = adapter.execute_preview(self._request)
            self.result_ready.emit(result)
        except Exception as exc:  # noqa: BLE001  # Worker boundary: normalize worker exceptions into failed QueryResult
            self.result_ready.emit(
                QueryResult(
                    request_id=self._request.request_id,
                    status=ExecutionStatus.FAILED,
                    frame=None,
                    execution_seconds=0.0,
                    preview_row_count=0,
                    total_row_count=None,
                    truncated=False,
                    completed_at=datetime.now(UTC),
                    error_type="execution_worker_failed",
                    error_message=str(exc),
                )
            )
        finally:
            if adapter is not None:
                try:
                    adapter.close()
                except Exception:  # noqa: BLE001, S110  # Cleanup boundary: best effort adapter close
                    pass


__all__ = ["ExecutionWorker"]
