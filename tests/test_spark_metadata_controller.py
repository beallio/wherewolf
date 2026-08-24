from __future__ import annotations

from dataclasses import dataclass
from time import monotonic, sleep

from PyQt6.QtCore import QThread, pyqtSignal

from wherewolf.desktop.spark_metadata_controller import SparkMetadataController
from wherewolf.desktop.workers.spark_metadata_worker import SparkMetadataWorker
from wherewolf.services.spark_function_metadata import SparkFunctionMetadata


@dataclass(frozen=True)
class _Metadata:
    all_functions: tuple[object, ...]
    loaded: bool


class _Worker(QThread):
    metadata_ready = pyqtSignal(object)

    def __init__(self, metadata: _Metadata) -> None:
        super().__init__()
        self._metadata = metadata

    def run(self) -> None:
        self.metadata_ready.emit(self._metadata)


def test_spark_metadata_controller_starts_one_worker_and_reports_loaded_status(qtbot) -> None:
    worker = _Worker(_Metadata(all_functions=(object(), object()), loaded=True))
    factory_calls = 0

    def worker_factory() -> _Worker:
        nonlocal factory_calls
        factory_calls += 1
        return worker

    controller = SparkMetadataController(worker_factory=worker_factory)
    statuses: list[str] = []
    results: list[SparkFunctionMetadata] = []
    controller.status_changed.connect(statuses.append)
    controller.metadata_ready.connect(results.append)

    assert controller.ensure_started() is True
    assert controller.ensure_started() is False
    qtbot.waitUntil(lambda: len(results) == 1)

    assert statuses == [
        "Loading local Spark SQL function metadata...",
        "Loaded 2 local Spark SQL functions for completion",
    ]
    assert results == [worker._metadata]
    assert factory_calls == 1
    assert controller.shutdown() is True


def test_spark_metadata_controller_reports_curated_fallback_once(qtbot) -> None:
    worker = _Worker(_Metadata(all_functions=(object(),), loaded=False))
    controller = SparkMetadataController(worker_factory=lambda: worker)
    statuses: list[str] = []
    controller.status_changed.connect(statuses.append)

    assert controller.ensure_started() is True
    qtbot.waitUntil(lambda: len(statuses) == 2)
    assert statuses[-1] == "Spark SQL completion is using the curated fallback"
    assert controller.ensure_started() is False
    assert controller.shutdown() is True


def test_spark_metadata_worker_failure_keeps_the_curated_fallback(qtbot) -> None:
    def failing_loader() -> SparkFunctionMetadata:
        raise RuntimeError("Spark startup failed")

    worker = SparkMetadataWorker(loader=failing_loader)
    results: list[SparkFunctionMetadata] = []
    worker.metadata_ready.connect(results.append)
    worker.start()
    qtbot.waitUntil(lambda: len(results) == 1)

    assert results[0].loaded is False


def test_spark_metadata_controller_starts_promptly_and_discards_late_results(qtbot) -> None:
    def slow_loader() -> SparkFunctionMetadata:
        sleep(0.1)
        return SparkFunctionMetadata((), (), (), loaded=True)

    worker = SparkMetadataWorker(loader=slow_loader)
    controller = SparkMetadataController(worker_factory=lambda: worker)
    results: list[object] = []
    controller.metadata_ready.connect(results.append)

    started_at = monotonic()
    assert controller.ensure_started() is True
    assert monotonic() - started_at < 0.05
    assert controller.shutdown(timeout_ms=1) is False
    qtbot.waitUntil(lambda: not worker.isRunning())

    assert results == []
