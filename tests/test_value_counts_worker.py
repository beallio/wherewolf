from pathlib import Path
from uuid import uuid4

from PyQt6.QtTest import QSignalSpy

from wherewolf.desktop.workers.value_counts_worker import ValueCountsWorker
from wherewolf.domain import CatalogBinding
from wherewolf.domain.enums import EngineKind, SourceFormat


class _FakeAdapter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []
        self.closed = False

    def value_counts(self, entry, column_name: str, limit: int):
        self.calls.append((column_name, limit))
        return (("a", 4), ("b", 2), ("c", 1)), 3, 10

    def close(self) -> None:
        self.closed = True


class _FakeRegistry:
    def __init__(self, adapter: _FakeAdapter) -> None:
        self.adapter = adapter
        self.calls = []

    def create(self, kind: EngineKind, request_id):
        self.calls.append((kind, request_id))
        return self.adapter


def test_value_counts_worker_orders_counts_honours_limit_and_closes_adapter(qtbot) -> None:
    adapter = _FakeAdapter()
    registry = _FakeRegistry(adapter)
    binding = CatalogBinding(uuid4(), "users", Path("users.csv"), SourceFormat.CSV)
    worker = ValueCountsWorker(registry, binding, "category", 2)
    spy = QSignalSpy(worker.result_ready)

    with qtbot.waitSignal(worker.result_ready, timeout=2000):
        worker.start()
    assert worker.wait(5000)

    result = spy[0][0]
    assert adapter.calls == [("category", 2)]
    assert [item.value for item in result.counts] == ["a", "b", "c"]
    assert [item.count for item in result.counts] == [4, 2, 1]
    assert [item.percentage for item in result.counts] == [40.0, 20.0, 10.0]
    assert result.total_distinct == 3
    assert adapter.closed
