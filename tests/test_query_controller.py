from datetime import UTC, datetime
from uuid import uuid4

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtTest import QSignalSpy

from wherewolf.desktop.query_controller import QueryController
from wherewolf.domain import ExecutionRequest, ExecutionStatus, QueryResult
from wherewolf.domain.enums import EngineKind


class _FakeWorker(QObject):
    handle_published = pyqtSignal(object)
    result_ready = pyqtSignal(object)

    def __init__(self, request: ExecutionRequest):
        super().__init__()
        self.request = request
        self.started = False

    def start(self):
        self.started = True


class _FakeWorkerFactory:
    def __init__(self):
        self.created_workers = []

    def __call__(self, engine_registry, request):
        worker = _FakeWorker(request)
        self.created_workers.append(worker)
        return worker


class _FakeCancellationHandle:
    def __init__(self, request_id):
        self.request_id = request_id
        self.cancel_called = False

    def cancel(self) -> bool:
        self.cancel_called = True
        return True


def _make_request(sql: str = "SELECT 1") -> ExecutionRequest:
    return ExecutionRequest(
        request_id=uuid4(),
        engine=EngineKind.DUCKDB,
        source_dialect="duckdb",
        original_sql=sql,
        executable_sql=sql,
        catalog=(),
        preview_limit=1000,
        submitted_at=datetime.now(UTC),
    )


def test_query_controller_initial_state():
    controller = QueryController(engine_registry=None)
    assert controller.status is ExecutionStatus.IDLE
    assert controller.active_request is None


def test_query_controller_run_transitions_to_running(qtbot):
    factory = _FakeWorkerFactory()
    controller = QueryController(engine_registry=None, worker_factory=factory)

    status_spy = QSignalSpy(controller.status_changed)
    req = _make_request()

    assert controller.execute(req) is True
    assert controller.status is ExecutionStatus.RUNNING
    assert controller.active_request == req
    assert len(factory.created_workers) == 1
    assert factory.created_workers[0].started is True

    # State sequence: RUNNING emitted
    assert len(status_spy) == 1
    assert status_spy[0][0] is ExecutionStatus.RUNNING


def test_query_controller_second_run_refused_while_active(qtbot):
    factory = _FakeWorkerFactory()
    controller = QueryController(engine_registry=None, worker_factory=factory)

    req1 = _make_request("SELECT 1")
    req2 = _make_request("SELECT 2")

    assert controller.execute(req1) is True
    assert controller.execute(req2) is False
    assert controller.active_request == req1


def test_query_controller_success_flow(qtbot):
    import polars as pl

    factory = _FakeWorkerFactory()
    controller = QueryController(engine_registry=None, worker_factory=factory)

    status_spy = QSignalSpy(controller.status_changed)
    result_spy = QSignalSpy(controller.result_ready)

    req = _make_request()
    controller.execute(req)

    worker = factory.created_workers[0]
    handle = _FakeCancellationHandle(req.request_id)
    worker.handle_published.emit(handle)

    success_result = QueryResult(
        request_id=req.request_id,
        status=ExecutionStatus.SUCCEEDED,
        frame=pl.DataFrame({"a": [1]}),
        execution_seconds=0.1,
        preview_row_count=1,
        total_row_count=None,
        truncated=False,
        completed_at=datetime.now(UTC),
    )

    worker.result_ready.emit(success_result)

    assert len(result_spy) == 1
    assert result_spy[0][0] == success_result

    # Transitions: RUNNING -> SUCCEEDED -> IDLE
    statuses = [call[0] for call in status_spy]
    assert statuses == [ExecutionStatus.RUNNING, ExecutionStatus.SUCCEEDED, ExecutionStatus.IDLE]
    assert controller.status is ExecutionStatus.IDLE
    assert controller.active_request is None


def test_query_controller_error_flow(qtbot):
    factory = _FakeWorkerFactory()
    controller = QueryController(engine_registry=None, worker_factory=factory)

    status_spy = QSignalSpy(controller.status_changed)
    result_spy = QSignalSpy(controller.result_ready)

    req = _make_request()
    controller.execute(req)

    worker = factory.created_workers[0]
    error_result = QueryResult(
        request_id=req.request_id,
        status=ExecutionStatus.FAILED,
        frame=None,
        execution_seconds=0.0,
        preview_row_count=0,
        total_row_count=None,
        truncated=False,
        completed_at=datetime.now(UTC),
        error_type="error",
        error_message="failed to run",
    )

    worker.result_ready.emit(error_result)

    assert len(result_spy) == 1
    assert result_spy[0][0] == error_result

    statuses = [call[0] for call in status_spy]
    assert statuses == [ExecutionStatus.RUNNING, ExecutionStatus.FAILED, ExecutionStatus.IDLE]
    assert controller.status is ExecutionStatus.IDLE


def test_query_controller_cancel_flow_transitions_to_cancellation_requested(qtbot):
    factory = _FakeWorkerFactory()
    controller = QueryController(engine_registry=None, worker_factory=factory)

    status_spy = QSignalSpy(controller.status_changed)

    req = _make_request()
    controller.execute(req)

    worker = factory.created_workers[0]
    handle = _FakeCancellationHandle(req.request_id)
    worker.handle_published.emit(handle)

    # Cancel moves state to CANCELLATION_REQUESTED (not straight to CANCELLED)
    assert controller.cancel() is True
    assert controller.status is ExecutionStatus.CANCELLATION_REQUESTED
    assert handle.cancel_called is True

    # Now worker completes with CANCELLED
    cancel_result = QueryResult(
        request_id=req.request_id,
        status=ExecutionStatus.CANCELLED,
        frame=None,
        execution_seconds=0.0,
        preview_row_count=0,
        total_row_count=None,
        truncated=False,
        completed_at=datetime.now(UTC),
    )
    worker.result_ready.emit(cancel_result)

    statuses = [call[0] for call in status_spy]
    assert statuses == [
        ExecutionStatus.RUNNING,
        ExecutionStatus.CANCELLATION_REQUESTED,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.IDLE,
    ]
    assert controller.status is ExecutionStatus.IDLE


def test_query_controller_cancel_requested_race_finished_first(qtbot):
    import polars as pl

    factory = _FakeWorkerFactory()
    controller = QueryController(engine_registry=None, worker_factory=factory)

    status_spy = QSignalSpy(controller.status_changed)

    req = _make_request()
    controller.execute(req)

    worker = factory.created_workers[0]
    controller.cancel()

    # Query finishes with SUCCEEDED before cancellation landed
    success_result = QueryResult(
        request_id=req.request_id,
        status=ExecutionStatus.SUCCEEDED,
        frame=pl.DataFrame({"x": [42]}),
        execution_seconds=0.1,
        preview_row_count=1,
        total_row_count=None,
        truncated=False,
        completed_at=datetime.now(UTC),
    )
    worker.result_ready.emit(success_result)

    statuses = [call[0] for call in status_spy]
    assert statuses == [
        ExecutionStatus.RUNNING,
        ExecutionStatus.CANCELLATION_REQUESTED,
        ExecutionStatus.SUCCEEDED,
        ExecutionStatus.IDLE,
    ]


def test_query_controller_ignores_stale_worker_signal(qtbot):
    import polars as pl

    factory = _FakeWorkerFactory()
    controller = QueryController(engine_registry=None, worker_factory=factory)

    result_spy = QSignalSpy(controller.result_ready)

    req1 = _make_request()
    controller.execute(req1)
    worker1 = factory.created_workers[0]

    # Stale result from a previous request_id
    stale_req_id = uuid4()
    stale_result = QueryResult(
        request_id=stale_req_id,
        status=ExecutionStatus.SUCCEEDED,
        frame=pl.DataFrame({"stale": [1]}),
        execution_seconds=0.1,
        preview_row_count=1,
        total_row_count=None,
        truncated=False,
        completed_at=datetime.now(UTC),
    )

    worker1.result_ready.emit(stale_result)

    # Controller ignored stale result: state remains RUNNING, active_request remains req1
    assert controller.status is ExecutionStatus.RUNNING
    assert controller.active_request == req1
    assert len(result_spy) == 0


class _ShutdownWorker(QThread):
    def __init__(self):
        super().__init__()
        self.quit_called = False
        self.wait_called = False

    def isRunning(self) -> bool:
        return True

    def quit(self) -> None:
        self.quit_called = True

    def wait(self, *args, **kwargs) -> bool:
        self.wait_called = True
        return True


def test_query_controller_shutdown():
    controller = QueryController(engine_registry=None)
    worker = _ShutdownWorker()
    controller._workers.append(worker)

    controller.shutdown()

    assert worker.quit_called is True
    assert worker.wait_called is True
    assert len(controller._workers) == 0
