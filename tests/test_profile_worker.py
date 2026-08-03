from pathlib import Path
from uuid import uuid4

from PyQt6.QtTest import QSignalSpy

from wherewolf.desktop.workers import ProfileWorker
from wherewolf.domain import CatalogBinding, ProfileResult
from wherewolf.domain.enums import EngineKind, SourceFormat


class _FakeAdapter:
    def __init__(self, result: ProfileResult) -> None:
        self._result = result
        self.closed = False

    def profile_dataset(self, entry) -> ProfileResult:
        return self._result

    def close(self) -> None:
        self.closed = True


class _FakeRegistry:
    def __init__(self, adapter: _FakeAdapter) -> None:
        self.adapter = adapter

    def create(self, kind: EngineKind, request_id) -> _FakeAdapter:
        assert kind is EngineKind.DUCKDB
        return self.adapter


def test_profile_worker_emits_profile_result_and_closes_adapter(qtbot) -> None:
    entry_id = uuid4()
    result = ProfileResult(entry_id=entry_id, profiles=())
    adapter = _FakeAdapter(result)
    worker = ProfileWorker(
        engine_registry=_FakeRegistry(adapter),
        binding=CatalogBinding(entry_id, "events", Path(__file__), SourceFormat.CSV),
    )
    spy = QSignalSpy(worker.result_ready)

    with qtbot.waitSignal(worker.result_ready, timeout=2000):
        worker.start()

    assert worker.wait(5000)
    assert spy[0][0] == result
    assert adapter.closed
