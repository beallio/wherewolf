from pathlib import Path
from uuid import uuid4

from PyQt6.QtTest import QSignalSpy

from wherewolf.desktop.workers import SchemaWorker
from wherewolf.domain import CatalogBinding, ColumnSchema, SchemaResult
from wherewolf.domain.enums import EngineKind, SourceFormat


class _FakeAdapter:
    def __init__(self, result: SchemaResult, should_fail: bool = False):
        self._result = result
        self.should_fail = should_fail
        self.closed = False

    def inspect_schema(self, entry) -> SchemaResult:
        if self.should_fail:
            raise RuntimeError("boom")
        return self._result

    def close(self) -> None:
        self.closed = True


class _FakeRegistry:
    def __init__(self, adapter: _FakeAdapter):
        self.adapter = adapter
        self.calls = []

    def create(self, kind: EngineKind, request_id) -> _FakeAdapter:
        self.calls.append((kind, request_id))
        return self.adapter


def test_schema_worker_emits_schema_result_and_closes_adapter(qtbot) -> None:
    result = SchemaResult(
        entry_id=uuid4(),
        columns=(ColumnSchema("a", "INTEGER"),),
    )
    adapter = _FakeAdapter(result)
    registry = _FakeRegistry(adapter)
    binding = CatalogBinding(
        entry_id=result.entry_id,
        alias="x",
        path=Path(__file__),
        source_format=SourceFormat.CSV,
    )

    worker = SchemaWorker(engine_registry=registry, binding=binding)
    spy = QSignalSpy(worker.result_ready)

    with qtbot.waitSignal(worker.result_ready, timeout=2000):
        worker.start()

    # result_ready is emitted from inside run(), before its finally block completes.
    # Without waiting for the thread to finish, the worker can be garbage collected
    # while still running, which makes Qt abort the interpreter. Waiting also makes
    # the adapter-closed assertion deterministic rather than racy.
    assert worker.wait(5000)

    assert len(spy) == 1
    emitted = spy[0][0]
    assert emitted == result
    assert adapter.closed
    assert registry.calls


def test_schema_worker_emits_error_result_on_exception_and_still_closes_adapter(qtbot) -> None:
    result_id = uuid4()
    adapter = _FakeAdapter(result=SchemaResult(entry_id=result_id, columns=None), should_fail=True)
    registry = _FakeRegistry(adapter)
    binding = CatalogBinding(
        entry_id=result_id,
        alias="x",
        path=Path(__file__),
        source_format=SourceFormat.CSV,
    )

    worker = SchemaWorker(engine_registry=registry, binding=binding)
    spy = QSignalSpy(worker.result_ready)

    with qtbot.waitSignal(worker.result_ready, timeout=2000):
        worker.start()

    # result_ready is emitted from inside run(), before its finally block completes.
    # Without waiting for the thread to finish, the worker can be garbage collected
    # while still running, which makes Qt abort the interpreter. Waiting also makes
    # the adapter-closed assertion deterministic rather than racy.
    assert worker.wait(5000)

    assert len(spy) == 1
    emitted = spy[0][0]
    assert emitted.entry_id == result_id
    assert emitted.columns is None
    assert emitted.error_type == "schema_worker_failed"
    assert "boom" in emitted.error_message
    assert adapter.closed
