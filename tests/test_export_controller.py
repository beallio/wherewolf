from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from uuid import uuid4

import polars as pl

from wherewolf.desktop.export_controller import ExportController
from wherewolf.domain import EngineKind, ExecutionRequest
from wherewolf.services.export_destination import ExportFormat, write_atomically


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


class _Handle:
    def __init__(self, request_id, cancelled: Event) -> None:
        self.request_id = request_id
        self._cancelled = cancelled

    def cancel(self) -> bool:
        self._cancelled.set()
        return True


class _BlockingAdapter:
    def __init__(self, request_id, handle_was_published: Event) -> None:
        self._request_id = request_id
        self._handle_was_published = handle_was_published
        self.cancelled = Event()

    def cancellation_handle(self) -> _Handle:
        return _Handle(self._request_id, self.cancelled)

    def export_full(self, _request, destination: Path, _format: str) -> tuple[str, ...]:
        assert self._handle_was_published.is_set(), (
            "export began before cancellation handle published"
        )

        def write_partial(temp_path: Path) -> None:
            temp_path.write_bytes(b"partial")
            assert self.cancelled.wait(timeout=3), "test did not cancel the export"
            raise RuntimeError("Export cancelled")

        write_atomically(destination, write_partial)
        return ()

    def close(self) -> None:
        pass


class _FailingAdapter(_BlockingAdapter):
    def export_full(self, _request, destination: Path, _format: str) -> tuple[str, ...]:
        del destination
        raise RuntimeError("disk unavailable")


class _Registry:
    def __init__(self, adapter) -> None:
        self.adapter = adapter

    def create(self, _engine, _request_id):
        return self.adapter


def test_preview_export_controller_emits_one_terminal_result(qtbot, tmp_path: Path) -> None:
    controller = ExportController()
    with qtbot.waitSignal(controller.result_ready, timeout=3000) as blocker:
        assert controller.export(
            None, pl.DataFrame({"id": [1]}), tmp_path / "out.csv", ExportFormat.CSV, False
        )
    assert blocker.args[0].succeeded
    controller.shutdown()


def test_full_export_publishes_handle_before_work_and_cancellation_preserves_destination(
    qtbot, tmp_path: Path
) -> None:
    published = Event()
    request = _request()
    adapter = _BlockingAdapter(request.request_id, published)
    controller = ExportController(engine_registry=_Registry(adapter))
    controller.handle_published.connect(lambda _handle: published.set())
    destination = tmp_path / "out.csv"
    destination.write_bytes(b"original")

    with qtbot.waitSignal(controller.handle_published, timeout=3000):
        assert controller.export(request, None, destination, ExportFormat.CSV, True)
    with qtbot.waitSignal(controller.result_ready, timeout=3000) as blocker:
        assert controller.cancel()

    assert not blocker.args[0].succeeded
    assert blocker.args[0].error_message == "Export cancelled"
    assert destination.read_bytes() == b"original"
    assert list(tmp_path.glob(".out.csv.*")) == []
    assert controller._worker is not None
    assert controller._worker.wait(3000)
    assert controller.cancel() is False
    controller.shutdown()


def test_full_export_failure_is_a_terminal_result_not_an_exception(qtbot, tmp_path: Path) -> None:
    request = _request()
    published = Event()
    controller = ExportController(
        engine_registry=_Registry(_FailingAdapter(request.request_id, published))
    )
    controller.handle_published.connect(lambda _handle: published.set())

    with qtbot.waitSignal(controller.result_ready, timeout=3000) as blocker:
        assert controller.export(request, None, tmp_path / "out.csv", ExportFormat.CSV, True)

    assert not blocker.args[0].succeeded
    assert blocker.args[0].error_message == "disk unavailable"
    controller.shutdown()
