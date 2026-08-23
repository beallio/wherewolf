"""Independent background lifecycle for fetching captured-query result pages."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from threading import Event

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from wherewolf.domain import ExecutionRequest, ExecutionStatus, PageResult

_MAX_DUCKDB_OFFSET = (1 << 63) - 1


class PageWorker(QThread):
    """Run one optional engine pagination capability behind a cancellation barrier."""

    handle_published = pyqtSignal(object)
    result_ready = pyqtSignal(object)

    def __init__(self, engine_registry, request: ExecutionRequest, page_index: int) -> None:
        super().__init__()
        self._registry = engine_registry
        self._request = request
        self._page_index = page_index
        self._handle_observed = Event()

    def permit_fetch(self) -> None:
        """Release page work only after the controller has its cancellation handle."""
        self._handle_observed.set()

    def run(self) -> None:  # pragma: no cover - exercised through controller tests
        adapter = None
        page_size = self._request.preview_limit
        offset = self._page_index * page_size
        result: PageResult
        try:
            adapter = self._registry.create(self._request.engine, self._request.request_id)
            self.handle_published.emit(adapter.cancellation_handle())
            self._handle_observed.wait()
            fetch_page = getattr(adapter, "fetch_page", None)
            if not callable(fetch_page):
                raise TypeError("Selected engine does not support result pagination")
            candidate = fetch_page(self._request, offset, page_size)
            if not isinstance(candidate, PageResult):
                raise TypeError("Page adapter returned an invalid result")
            if candidate.request_id != self._request.request_id:
                raise ValueError("Page adapter returned a result for a different request")
            if candidate.offset != offset or candidate.page_size != page_size:
                raise ValueError("Page adapter returned a result for a different page")
            result = candidate
        except Exception as error:  # noqa: BLE001 - adapter boundary must not escape a QThread.
            result = PageResult(
                request_id=self._request.request_id,
                status=ExecutionStatus.FAILED,
                frame=None,
                offset=offset,
                page_size=page_size,
                has_next=False,
                execution_seconds=0.0,
                completed_at=datetime.now(UTC),
                error_type=type(error).__name__,
                error_message=str(error),
            )
        finally:
            if adapter is not None:
                try:
                    adapter.close()
                except Exception:  # noqa: BLE001, S110 - cleanup must not suppress the terminal result.
                    pass
        self.result_ready.emit(result)


class PageController(QObject):
    """Own at most one result-page worker and expose its terminal domain result."""

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
        self._worker_factory = worker_factory or PageWorker
        self._worker: QThread | None = None
        self._handle = None
        self._active_request_id = None
        self._pending_cancel = False

    @property
    def fetching(self) -> bool:
        return self._worker is not None

    def fetch(self, request: ExecutionRequest, page_index: int) -> bool:
        """Fetch a zero-based page index from one captured query request."""
        page_size = request.preview_limit
        if self._worker is not None:
            return False
        if page_index < 0 or page_size <= 0:
            return False
        if page_index > _MAX_DUCKDB_OFFSET // page_size:
            return False

        worker = self._worker_factory(self._registry, request, page_index)
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
        """Request cancellation of the one active page fetch."""
        if self._worker is None or self._active_request_id is None:
            return False
        self._pending_cancel = True
        if self._handle is not None:
            self._handle.cancel()
        return True

    def shutdown(self) -> bool:
        """Cancel and wait for the active worker for at most five seconds."""
        worker = self._worker
        if worker is None:
            return True
        self.cancel()
        permit_fetch = getattr(worker, "permit_fetch", None)
        if callable(permit_fetch):
            permit_fetch()
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
        permit_fetch = getattr(worker, "permit_fetch", None)
        if callable(permit_fetch):
            permit_fetch()

    def _on_result(self, result: object) -> None:
        if not isinstance(result, PageResult):
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


__all__ = ["PageController", "PageWorker"]
