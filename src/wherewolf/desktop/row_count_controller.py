"""Independent background lifecycle for counting rows in a captured query request."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from threading import Event

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from wherewolf.domain import ExecutionRequest, ExecutionStatus, RowCountResult


class RowCountWorker(QThread):
    """Run one optional engine row-count capability behind a cancellation barrier."""

    handle_published = pyqtSignal(object)
    result_ready = pyqtSignal(object)

    def __init__(self, engine_registry, request: ExecutionRequest) -> None:
        super().__init__()
        self._registry = engine_registry
        self._request = request
        self._handle_observed = Event()

    def permit_count(self) -> None:
        """Release count work only after the controller has its cancellation handle."""
        self._handle_observed.set()

    def run(self) -> None:  # pragma: no cover - exercised through controller tests
        adapter = None
        result: RowCountResult
        try:
            adapter = self._registry.create(self._request.engine, self._request.request_id)
            self.handle_published.emit(adapter.cancellation_handle())
            self._handle_observed.wait()
            count_rows = getattr(adapter, "count_rows", None)
            if not callable(count_rows):
                raise TypeError("Selected engine does not support counting all rows")
            candidate = count_rows(self._request)
            if not isinstance(candidate, RowCountResult):
                raise TypeError("Row-count adapter returned an invalid result")
            if candidate.request_id != self._request.request_id:
                raise ValueError("Row-count adapter returned a result for a different request")
            result = candidate
        except Exception as error:  # noqa: BLE001  # Adapter boundary must not escape a QThread.
            result = RowCountResult(
                request_id=self._request.request_id,
                status=ExecutionStatus.FAILED,
                total_row_count=None,
                completed_at=datetime.now(UTC),
                error_type=type(error).__name__,
                error_message=str(error),
            )
        finally:
            if adapter is not None:
                try:
                    adapter.close()
                except Exception:  # noqa: BLE001, S110  # Cleanup must not suppress the terminal result.
                    pass
        self.result_ready.emit(result)


class RowCountController(QObject):
    """Own at most one row-count worker and expose its terminal domain result."""

    started = pyqtSignal()
    result_ready = pyqtSignal(object)
    handle_published = pyqtSignal(object)

    def __init__(
        self,
        engine_registry=None,
        worker_factory: Callable[..., QThread] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        if engine_registry is None:
            from wherewolf.execution.registry import EngineRegistry

            engine_registry = EngineRegistry()
        self._registry = engine_registry
        self._worker_factory = worker_factory or RowCountWorker
        self._worker: QThread | None = None
        self._handle = None
        self._active_request_id = None
        self._pending_cancel = False

    @property
    def counting(self) -> bool:
        return self._worker is not None

    def count(self, request: ExecutionRequest) -> bool:
        if self._worker is not None:
            return False
        worker = self._worker_factory(self._registry, request)
        self._worker = worker
        self._active_request_id = request.request_id
        self._handle = None
        self._pending_cancel = False
        handle_signal = getattr(worker, "handle_published", None)
        result_signal = getattr(worker, "result_ready", None)
        if handle_signal is not None:
            handle_signal.connect(self._on_handle)
        if result_signal is not None:
            result_signal.connect(self._on_result)
        worker.finished.connect(self._on_worker_finished)
        worker.start()
        self.started.emit()
        return True

    def cancel(self) -> bool:
        if self._worker is None or self._active_request_id is None:
            return False
        self._pending_cancel = True
        if self._handle is not None:
            self._handle.cancel()
        return True

    def shutdown(self) -> bool:
        worker = self._worker
        if worker is None:
            return True
        self.cancel()
        permit_count = getattr(worker, "permit_count", None)
        if callable(permit_count):
            permit_count()
        if worker.isRunning():
            worker.quit()
            stopped = worker.wait(5000)
        else:
            stopped = True
        self._worker = None
        self._handle = None
        self._active_request_id = None
        self._pending_cancel = False
        return stopped

    def _on_handle(self, handle) -> None:
        worker = self._worker
        if worker is None:
            return
        try:
            matching_handle = handle.request_id == self._active_request_id
        except AttributeError:
            matching_handle = False
        if matching_handle:
            self._handle = handle
            if self._pending_cancel:
                handle.cancel()
            self.handle_published.emit(handle)
        permit_count = getattr(worker, "permit_count", None)
        if callable(permit_count):
            permit_count()

    def _on_result(self, result: object) -> None:
        if not isinstance(result, RowCountResult):
            return
        if result.request_id != self._active_request_id:
            return
        self._handle = None
        self._active_request_id = None
        self._pending_cancel = False
        self.result_ready.emit(result)

    def _on_worker_finished(self) -> None:
        worker = self.sender()
        if worker is self._worker:
            self._worker = None


__all__ = ["RowCountController", "RowCountWorker"]
