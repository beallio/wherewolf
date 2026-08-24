"""Coordinate one asynchronous Spark metadata load for a desktop window."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from wherewolf.desktop.workers.spark_metadata_worker import SparkMetadataWorker


class SparkMetadataController(QObject):
    """Start one worker and publish non-blocking completion metadata status."""

    status_changed = pyqtSignal(str)
    metadata_ready = pyqtSignal(object)

    def __init__(
        self,
        *,
        worker_factory: Callable[[], QThread] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._worker_factory = worker_factory or SparkMetadataWorker
        self._worker: QThread | None = None
        self._started = False
        self._closed = False

    def ensure_started(self) -> bool:
        """Start discovery once, returning whether this call created the worker."""

        if self._started or self._closed:
            return False
        self._started = True
        worker = self._worker_factory()
        metadata_signal = getattr(worker, "metadata_ready", None)
        if metadata_signal is None:
            raise TypeError("Spark metadata worker must publish metadata_ready")
        metadata_signal.connect(self._on_metadata_ready)
        self._worker = worker
        self.status_changed.emit("Loading local Spark SQL function metadata...")
        worker.start()
        return True

    def shutdown(self, timeout_ms: int = 1000) -> bool:
        """Stop waiting for a worker after a bounded window during desktop shutdown."""

        self._closed = True
        worker = self._worker
        if worker is None or not worker.isRunning():
            return True
        worker.quit()
        return worker.wait(timeout_ms)

    def _on_metadata_ready(self, metadata: object) -> None:
        if self._closed:
            return
        self.metadata_ready.emit(metadata)
        if bool(getattr(metadata, "loaded", False)):
            function_count = len(getattr(metadata, "all_functions", ()))
            self.status_changed.emit(
                f"Loaded {function_count} local Spark SQL functions for completion"
            )
        else:
            self.status_changed.emit("Spark SQL completion is using the curated fallback")


__all__ = ["SparkMetadataController"]
