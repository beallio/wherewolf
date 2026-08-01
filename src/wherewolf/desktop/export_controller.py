"""Background controller for path-based desktop exports."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from wherewolf.domain import ExecutionRequest
from wherewolf.services.export_destination import ExportFormat
from wherewolf.services.preview_export import write_preview


@dataclass(frozen=True, slots=True)
class ExportResult:
    destination: Path
    succeeded: bool
    error_message: str | None = None
    warnings: tuple[str, ...] = ()


class ExportWorker(QThread):
    handle_published = pyqtSignal(object)
    result_ready = pyqtSignal(object)

    def __init__(
        self,
        registry,
        request: ExecutionRequest | None,
        frame,
        destination: Path,
        export_format: ExportFormat,
        full_export: bool,
    ) -> None:
        super().__init__()
        self._registry, self._request, self._frame = registry, request, frame
        self._destination, self._format, self._full_export = destination, export_format, full_export

    def run(self) -> None:  # pragma: no cover - exercised through controller tests
        adapter = None
        try:
            if self._full_export:
                assert self._request is not None
                adapter = self._registry.create(self._request.engine, self._request.request_id)
                self.handle_published.emit(adapter.cancellation_handle())
                export_full = getattr(adapter, "export_full", None)
                if export_full is None:
                    raise ValueError("Selected engine does not support full export")
                warnings = export_full(self._request, self._destination, self._format.value)
            else:
                write_preview(self._frame, self._destination, self._format)
                warnings = ()
            self.result_ready.emit(ExportResult(self._destination, True, warnings=warnings))
        except Exception as exc:  # noqa: BLE001
            self.result_ready.emit(ExportResult(self._destination, False, str(exc)))
        finally:
            if adapter is not None:
                adapter.close()


class ExportController(QObject):
    started = pyqtSignal()
    result_ready = pyqtSignal(object)
    handle_published = pyqtSignal(object)

    def __init__(
        self,
        engine_registry=None,
        worker_factory: Callable[..., QThread] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._registry, self._worker_factory = engine_registry, worker_factory or ExportWorker
        self._worker: QThread | None = None
        self._handle = None

    @property
    def exporting(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def export(
        self, request, frame, destination: Path, export_format: ExportFormat, full_export: bool
    ) -> bool:
        if self.exporting:
            return False
        worker = self._worker_factory(
            self._registry, request, frame, destination, export_format, full_export
        )
        self._worker = worker
        handle_signal = getattr(worker, "handle_published", None)
        result_signal = getattr(worker, "result_ready", None)
        if handle_signal is not None:
            handle_signal.connect(self._on_handle)
        if result_signal is not None:
            result_signal.connect(self._on_result)
        worker.start()
        self.started.emit()
        return True

    def cancel(self) -> bool:
        if not self.exporting or self._handle is None:
            return False
        self._handle.cancel()
        return True

    def shutdown(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait()
        self._worker = None

    def _on_handle(self, handle) -> None:
        self._handle = handle
        self.handle_published.emit(handle)

    def _on_result(self, result: ExportResult) -> None:
        self._handle = None
        self.result_ready.emit(result)
