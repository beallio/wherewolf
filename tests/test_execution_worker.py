from datetime import UTC
from uuid import uuid4

from PyQt6.QtTest import QSignalSpy

from wherewolf.desktop.workers.execution_worker import ExecutionWorker
from wherewolf.domain import ExecutionRequest, ExecutionStatus, QueryResult, SchemaResult
from wherewolf.domain.enums import EngineKind
from wherewolf.execution.base import CancellationHandle


class _FakeHandle:
    def __init__(self, request_id):
        self.request_id = request_id
        self.cancelled = False

    def cancel(self) -> bool:
        self.cancelled = True
        return True


class _FakeExecutionAdapter:
    def __init__(self, result: QueryResult, should_fail: bool = False):
        self._result = result
        self.should_fail = should_fail
        self.handle = _FakeHandle(result.request_id)
        self.closed = False
        self.execute_called = False

    def cancellation_handle(self) -> CancellationHandle:
        return self.handle  # type: ignore[return-value]

    def execute_preview(self, request: ExecutionRequest) -> QueryResult:
        self.execute_called = True
        if self.should_fail:
            raise RuntimeError("engine execution crashed")
        return self._result

    def inspect_schema(self, entry: object) -> SchemaResult:
        return SchemaResult(entry_id=uuid4(), columns=())

    def close(self) -> None:
        self.closed = True


class _FakeExecutionRegistry:
    def __init__(self, adapter: _FakeExecutionAdapter):
        self.adapter = adapter
        self.calls = []

    def create(self, kind: EngineKind, request_id) -> _FakeExecutionAdapter:
        self.calls.append((kind, request_id))
        return self.adapter


def test_execution_worker_publishes_handle_emits_result_and_closes(qtbot) -> None:
    from datetime import datetime

    req_id = uuid4()
    req = ExecutionRequest(
        request_id=req_id,
        engine=EngineKind.DUCKDB,
        source_dialect="duckdb",
        original_sql="SELECT 1",
        executable_sql="SELECT 1",
        catalog=(),
        preview_limit=1000,
        submitted_at=datetime.now(UTC),
    )
    import polars as pl

    result = QueryResult(
        request_id=req_id,
        status=ExecutionStatus.SUCCEEDED,
        frame=pl.DataFrame({"a": [1]}),
        execution_seconds=0.1,
        preview_row_count=1,
        total_row_count=None,
        truncated=False,
        completed_at=datetime.now(UTC),
    )

    adapter = _FakeExecutionAdapter(result)
    registry = _FakeExecutionRegistry(adapter)

    worker = ExecutionWorker(engine_registry=registry, request=req)  # type: ignore[arg-type]
    handle_spy = QSignalSpy(worker.handle_published)
    result_spy = QSignalSpy(worker.result_ready)

    with qtbot.waitSignal(worker.result_ready, timeout=2000):
        worker.start()

    assert worker.wait(5000)

    assert len(handle_spy) == 1
    assert handle_spy[0][0] is adapter.handle
    assert adapter.execute_called is True

    assert len(result_spy) == 1
    assert result_spy[0][0] == result
    assert adapter.closed is True


def test_execution_worker_emits_error_result_on_exception_and_closes(qtbot) -> None:
    from datetime import datetime

    req_id = uuid4()
    req = ExecutionRequest(
        request_id=req_id,
        engine=EngineKind.DUCKDB,
        source_dialect="duckdb",
        original_sql="SELECT 1",
        executable_sql="SELECT 1",
        catalog=(),
        preview_limit=1000,
        submitted_at=datetime.now(UTC),
    )
    result = QueryResult(
        request_id=req_id,
        status=ExecutionStatus.FAILED,
        frame=None,
        execution_seconds=0.0,
        preview_row_count=0,
        total_row_count=None,
        truncated=False,
        completed_at=datetime.now(UTC),
        error_type="failed",
        error_message="failed",
    )
    adapter = _FakeExecutionAdapter(result, should_fail=True)
    registry = _FakeExecutionRegistry(adapter)

    worker = ExecutionWorker(engine_registry=registry, request=req)  # type: ignore[arg-type]
    result_spy = QSignalSpy(worker.result_ready)

    with qtbot.waitSignal(worker.result_ready, timeout=2000):
        worker.start()

    assert worker.wait(5000)

    assert len(result_spy) == 1
    emitted = result_spy[0][0]
    assert emitted.request_id == req_id
    assert emitted.status is ExecutionStatus.FAILED
    assert emitted.error_type == "execution_worker_failed"
    assert "engine execution crashed" in emitted.error_message
    assert adapter.closed is True
