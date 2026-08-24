"""Background loader for the local Spark SQL function catalog."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from wherewolf.services.spark_function_metadata import (
    SparkFunctionMetadata,
    current_spark_function_metadata,
    load_spark_function_metadata,
)


class SparkMetadataWorker(QThread):
    """Load immutable Spark metadata without touching desktop widgets."""

    metadata_ready = pyqtSignal(object)

    def __init__(
        self,
        loader: Callable[[], SparkFunctionMetadata] = load_spark_function_metadata,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._loader = loader

    def run(self) -> None:  # pragma: no cover - exercised through controller integration tests
        try:
            metadata = self._loader()
        except Exception:  # noqa: BLE001 - the editor must retain its curated fallback
            metadata = current_spark_function_metadata()
        self.metadata_ready.emit(metadata)


__all__ = ["SparkMetadataWorker"]
