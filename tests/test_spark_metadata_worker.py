from __future__ import annotations

from wherewolf.desktop.workers.spark_metadata_worker import SparkMetadataWorker
from wherewolf.services.spark_function_metadata import SparkFunctionMetadata


def test_spark_metadata_worker_publishes_immutable_loader_result(qtbot) -> None:
    metadata = SparkFunctionMetadata((), (), (), loaded=True)
    worker = SparkMetadataWorker(loader=lambda: metadata)
    results: list[SparkFunctionMetadata] = []
    worker.metadata_ready.connect(results.append)

    worker.start()
    qtbot.waitUntil(lambda: results == [metadata])

    assert results[0] is metadata
