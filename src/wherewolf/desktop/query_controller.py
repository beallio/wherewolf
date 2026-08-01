"""Execution state machine and query controller for PyQt desktop shell."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from wherewolf.desktop.workers.execution_worker import ExecutionWorker
from wherewolf.domain import ExecutionRequest, ExecutionStatus, QueryResult
from wherewolf.execution.base import CancellationHandle


class EngineRegistryProtocol(Protocol):
    pass


class QueryController(QObject):
    """Manages query execution state machine transitions and background workers."""

    status_changed = pyqtSignal(ExecutionStatus)
    result_ready = pyqtSignal(QueryResult)
    handle_published = pyqtSignal(object)

    def __init__(
        self,
        engine_registry: EngineRegistryProtocol | None = None,
        worker_factory: Callable[[object, ExecutionRequest], QThread] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._engine_registry = engine_registry
        self._worker_factory = worker_factory or (
            lambda reg, req: ExecutionWorker(engine_registry=reg, request=req)  # type: ignore[arg-type]
        )
        self._status = ExecutionStatus.IDLE
        self._active_request: ExecutionRequest | None = None
        self._active_handle: CancellationHandle | None = None
        self._active_worker: QThread | None = None

    @property
    def status(self) -> ExecutionStatus:
        return self._status

    @property
    def active_request(self) -> ExecutionRequest | None:
        return self._active_request

    @property
    def active_handle(self) -> CancellationHandle | None:
        return self._active_handle

    def execute(self, request: ExecutionRequest) -> bool:
        """Submit a query request for execution.

        Returns True if execution started, or False if another query is already active.
        """
        if self._status is not ExecutionStatus.IDLE:
            return False

        self._active_request = request
        self._status = ExecutionStatus.RUNNING
        self.status_changed.emit(ExecutionStatus.RUNNING)

        worker = self._worker_factory(self._engine_registry, request)
        handle_pub = getattr(worker, "handle_published", None)
        if handle_pub is not None:
            handle_pub.connect(self._on_handle_published)
        result_sig = getattr(worker, "result_ready", None)
        if result_sig is not None:
            result_sig.connect(self._on_result_ready)

        self._active_worker = worker
        worker.start()
        return True

    def cancel(self) -> bool:
        """Request cancellation of the active query.

        Returns True if cancellation was requested, or False if no query is active.
        """
        if self._status not in (ExecutionStatus.RUNNING, ExecutionStatus.CANCELLATION_REQUESTED):
            return False

        self._status = ExecutionStatus.CANCELLATION_REQUESTED
        self.status_changed.emit(ExecutionStatus.CANCELLATION_REQUESTED)

        if self._active_handle is not None:
            try:
                self._active_handle.cancel()
            except Exception:  # noqa: BLE001, S110  # Cancellation boundary: ignore handle failure
                pass

        return True

    def _on_handle_published(self, handle: object) -> None:
        if (
            self._active_request is not None
            and getattr(handle, "request_id", None) == self._active_request.request_id
        ):
            self._active_handle = handle  # type: ignore
            self.handle_published.emit(handle)

    def _on_result_ready(self, result: QueryResult) -> None:
        if self._active_request is None or result.request_id != self._active_request.request_id:
            # Ignore stale worker signal
            return

        terminal_status = result.status
        self._status = terminal_status
        self.status_changed.emit(terminal_status)
        self.result_ready.emit(result)

        self._active_request = None
        self._active_handle = None
        self._active_worker = None

        self._status = ExecutionStatus.IDLE
        self.status_changed.emit(ExecutionStatus.IDLE)


__all__ = ["QueryController"]
