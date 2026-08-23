from __future__ import annotations

from datetime import UTC, datetime
from threading import Event
from uuid import uuid4

import pytest
from PyQt6.QtCore import QThread, pyqtSignal

from wherewolf.desktop.row_count_controller import RowCountController
from wherewolf.domain import EngineKind, ExecutionRequest, ExecutionStatus, RowCountResult


def _request() -> ExecutionRequest:
    return ExecutionRequest(
        request_id=uuid4(),
        engine=EngineKind.DUCKDB,
        source_dialect="duckdb",
        original_sql="SELECT 1",
        executable_sql="SELECT 1",
        catalog=(),
        preview_limit=1,
        submitted_at=datetime.now(UTC),
    )


def _result(request: ExecutionRequest, status: ExecutionStatus) -> RowCountResult:
    if status is ExecutionStatus.SUCCEEDED:
        return RowCountResult(
            request_id=request.request_id,
            status=status,
            total_row_count=1,
            completed_at=datetime.now(UTC),
        )
    if status is ExecutionStatus.CANCELLED:
        return RowCountResult(
            request_id=request.request_id,
            status=status,
            total_row_count=None,
            completed_at=datetime.now(UTC),
        )
    return RowCountResult(
        request_id=request.request_id,
        status=status,
        total_row_count=None,
        completed_at=datetime.now(UTC),
        error_type="RuntimeError",
        error_message="count failed",
    )


class _Handle:
    def __init__(self, request_id) -> None:
        self.request_id = request_id
        self.cancelled = Event()
        self.cancel_calls = 0

    def cancel(self) -> bool:
        self.cancel_calls += 1
        self.cancelled.set()
        return True


class _Adapter:
    def __init__(self, request: ExecutionRequest, *, failure: Exception | None = None) -> None:
        self.request = request
        self.failure = failure
        self.handle = _Handle(request.request_id)
        self.count_started = Event()
        self.closed = 0

    def cancellation_handle(self) -> _Handle:
        return self.handle

    def count_rows(self, request: ExecutionRequest) -> RowCountResult:
        self.count_started.set()
        if self.failure is not None:
            raise self.failure
        return _result(
            request,
            ExecutionStatus.CANCELLED
            if self.handle.cancelled.is_set()
            else ExecutionStatus.SUCCEEDED,
        )

    def close(self) -> None:
        self.closed += 1


class _BlockingAdapter(_Adapter):
    def count_rows(self, request: ExecutionRequest) -> RowCountResult:
        self.count_started.set()
        assert self.handle.cancelled.wait(timeout=3), "test did not cancel the count"
        return _result(request, ExecutionStatus.CANCELLED)


class _Registry:
    def __init__(self, adapter: _Adapter) -> None:
        self.adapter = adapter

    def create(self, _engine, _request_id):
        return self.adapter


class _SequenceRegistry:
    def __init__(self, *adapters: _Adapter) -> None:
        self._adapters = iter(adapters)

    def create(self, _engine, _request_id) -> _Adapter:
        return next(self._adapters)


class _ScriptedWorker(QThread):
    handle_published = pyqtSignal(object)
    result_ready = pyqtSignal(object)

    def __init__(
        self, _registry, request: ExecutionRequest, results: tuple[RowCountResult, ...]
    ) -> None:
        super().__init__()
        self.request = request
        self.results = results
        self.handle = _Handle(request.request_id)
        self._permitted = Event()

    def permit_count(self) -> None:
        self._permitted.set()

    def run(self) -> None:  # pragma: no cover - asserted by the controller-facing tests
        self.handle_published.emit(self.handle)
        assert self._permitted.wait(timeout=3)
        for result in self.results:
            self.result_ready.emit(result)


class _WorkerFactory:
    def __init__(self, results: tuple[RowCountResult, ...]) -> None:
        self.results = results
        self.worker: _ScriptedWorker | None = None

    def __call__(self, registry, request: ExecutionRequest) -> _ScriptedWorker:
        del registry
        self.worker = _ScriptedWorker(None, request, self.results)
        return self.worker


class _DelayedHandleWorker(_ScriptedWorker):
    def __init__(self, _registry, request: ExecutionRequest) -> None:
        super().__init__(None, request, (_result(request, ExecutionStatus.SUCCEEDED),))
        self.ready_to_publish = Event()
        self.release_handle = Event()

    def run(self) -> None:  # pragma: no cover - asserted by the controller-facing tests
        self.ready_to_publish.set()
        assert self.release_handle.wait(timeout=3)
        super().run()


class _DelayedWorkerFactory:
    def __init__(self) -> None:
        self.worker: _DelayedHandleWorker | None = None

    def __call__(self, registry, request: ExecutionRequest) -> _DelayedHandleWorker:
        del registry
        self.worker = _DelayedHandleWorker(None, request)
        return self.worker


def test_row_count_controller_starts_one_worker_and_publishes_handle_before_count(qtbot) -> None:
    request = _request()
    adapter = _Adapter(request)
    controller = RowCountController(engine_registry=_Registry(adapter))
    handles: list[object] = []
    controller.handle_published.connect(handles.append)

    with qtbot.waitSignal(controller.result_ready, timeout=3000) as blocker:
        assert controller.count(request) is True
        assert controller.count(_request()) is False

    result = blocker.args[0]
    assert result.request_id == request.request_id
    assert result.status is ExecutionStatus.SUCCEEDED
    assert handles == [adapter.handle]
    assert adapter.count_started.is_set()
    assert adapter.closed == 1
    assert controller.shutdown() is True


def test_row_count_worker_normalizes_raised_failure_and_closes_once(qtbot) -> None:
    request = _request()
    adapter = _Adapter(request, failure=RuntimeError("disk unavailable"))
    controller = RowCountController(engine_registry=_Registry(adapter))

    with qtbot.waitSignal(controller.result_ready, timeout=3000) as blocker:
        assert controller.count(request)

    result = blocker.args[0]
    assert result.request_id == request.request_id
    assert result.status is ExecutionStatus.FAILED
    assert result.error_message == "disk unavailable"
    assert adapter.closed == 1
    assert controller.shutdown() is True


@pytest.mark.parametrize("first_terminal", (ExecutionStatus.FAILED, ExecutionStatus.CANCELLED))
def test_row_count_controller_reuses_one_controller_after_terminal_result(
    qtbot, first_terminal: ExecutionStatus
) -> None:
    first_request = _request()
    second_request = _request()
    first_adapter: _Adapter
    if first_terminal is ExecutionStatus.FAILED:
        first_adapter = _Adapter(first_request, failure=RuntimeError("disk unavailable"))
    else:
        first_adapter = _BlockingAdapter(first_request)
    second_adapter = _Adapter(second_request)
    controller = RowCountController(
        engine_registry=_SequenceRegistry(first_adapter, second_adapter)
    )
    results: list[RowCountResult] = []
    controller.result_ready.connect(results.append)

    with qtbot.waitSignal(controller.result_ready, timeout=3000) as first_completion:
        assert controller.count(first_request)
        if first_terminal is ExecutionStatus.CANCELLED:
            qtbot.waitUntil(first_adapter.count_started.is_set, timeout=3000)
            assert controller.cancel() is True

    assert first_completion.args[0].request_id == first_request.request_id
    assert first_completion.args[0].status is first_terminal
    assert first_adapter.closed == 1
    qtbot.waitUntil(lambda: not controller.counting, timeout=3000)

    with qtbot.waitSignal(controller.result_ready, timeout=3000) as second_completion:
        assert controller.count(second_request)

    assert second_completion.args[0].request_id == second_request.request_id
    assert second_completion.args[0].status is ExecutionStatus.SUCCEEDED
    assert second_adapter.closed == 1
    qtbot.waitUntil(lambda: not controller.counting, timeout=3000)
    assert [result.request_id for result in results] == [
        first_request.request_id,
        second_request.request_id,
    ]
    assert controller.shutdown() is True


def test_row_count_controller_cancels_before_and_after_handle_publication(qtbot) -> None:
    request = _request()
    factory = _DelayedWorkerFactory()
    controller = RowCountController(worker_factory=factory)

    assert controller.count(request)
    assert factory.worker is not None
    qtbot.waitUntil(factory.worker.ready_to_publish.is_set, timeout=3000)
    assert controller.cancel() is True
    with qtbot.waitSignal(controller.result_ready, timeout=3000) as blocker:
        factory.worker.release_handle.set()

    assert blocker.args[0].status is ExecutionStatus.SUCCEEDED
    assert factory.worker.handle.cancel_calls == 1
    assert controller.cancel() is False

    second_request = _request()
    adapter = _BlockingAdapter(second_request)
    second = RowCountController(engine_registry=_Registry(adapter))
    with qtbot.waitSignal(second.handle_published, timeout=3000):
        assert second.count(second_request)
    with qtbot.waitSignal(second.result_ready, timeout=3000) as cancelled:
        assert second.cancel() is True
    assert cancelled.args[0].status is ExecutionStatus.CANCELLED
    assert adapter.closed == 1
    assert second.shutdown() is True


def test_row_count_controller_ignores_mismatched_worker_results(qtbot) -> None:
    request = _request()
    mismatched = _result(_request(), ExecutionStatus.SUCCEEDED)
    factory = _WorkerFactory((mismatched, _result(request, ExecutionStatus.SUCCEEDED)))
    controller = RowCountController(worker_factory=factory)
    results: list[RowCountResult] = []
    controller.result_ready.connect(results.append)

    with qtbot.waitSignal(controller.result_ready, timeout=3000):
        assert controller.count(request)

    assert len(results) == 1
    assert results[0].request_id == request.request_id
    assert results[0].status is ExecutionStatus.SUCCEEDED
    assert results[0].total_row_count == 1
    assert controller.shutdown() is True


def test_row_count_controller_shutdown_cancels_and_waits_for_active_thread(qtbot) -> None:
    request = _request()
    adapter = _BlockingAdapter(request)
    controller = RowCountController(engine_registry=_Registry(adapter))

    with qtbot.waitSignal(controller.handle_published, timeout=3000):
        assert controller.count(request)
    assert controller.shutdown() is True
    assert adapter.handle.cancel_calls == 1
    assert adapter.closed == 1
    assert not controller.counting
