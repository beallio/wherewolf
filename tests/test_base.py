from datetime import UTC, datetime
from uuid import UUID, uuid4

import polars as pl

from wherewolf.domain import (
    CatalogBinding,
    CatalogEntry,
    ExecutionRequest,
    ExecutionStatus,
    QueryResult,
    SourceFormat,
)
from wherewolf.domain.models import SchemaResult
from wherewolf.execution.base import CancellationHandle, ExecutionEngine


def _request() -> ExecutionRequest:
    binding = CatalogBinding(
        entry_id=uuid4(),
        alias="dataset",
        path=__import__("pathlib").Path("data.csv"),
        source_format=SourceFormat.CSV,
    )
    return ExecutionRequest(
        request_id=uuid4(),
        engine=__import__("wherewolf.domain").domain.EngineKind.DUCKDB,
        source_dialect="duckdb",
        original_sql="SELECT 1",
        executable_sql="SELECT 1",
        catalog=(binding,),
        preview_limit=1000,
        submitted_at=datetime.now(tz=UTC),
    )


class FakeHandle:
    def __init__(self, request_id: UUID):
        self.request_id = request_id

    def cancel(self) -> bool:
        return True


class FakeEngine:
    def __init__(self):
        self._handle = FakeHandle(UUID(int=0))

    def execute_preview(self, request: ExecutionRequest) -> QueryResult:
        return QueryResult(
            request_id=request.request_id,
            status=ExecutionStatus.SUCCEEDED,
            frame=pl.DataFrame(),
            execution_seconds=0.0,
            preview_row_count=0,
            total_row_count=0,
            truncated=False,
            completed_at=datetime.now(tz=UTC),
        )

    def inspect_schema(self, entry: CatalogEntry) -> SchemaResult:
        return SchemaResult(entry_id=entry.id, columns=())

    def cancellation_handle(self) -> CancellationHandle:
        return self._handle

    def close(self) -> None:
        return None


def test_protocols_are_runtime_checkable() -> None:
    assert isinstance(FakeHandle(UUID(int=0)), CancellationHandle)
    assert isinstance(FakeEngine(), ExecutionEngine)


class MissingClose:
    def execute_preview(self, request: ExecutionRequest) -> QueryResult:
        return QueryResult(
            request_id=request.request_id,
            status=ExecutionStatus.SUCCEEDED,
            frame=pl.DataFrame(),
            execution_seconds=0.0,
            preview_row_count=0,
            total_row_count=0,
            truncated=False,
            completed_at=datetime.now(tz=UTC),
        )

    def inspect_schema(self, entry: CatalogEntry) -> SchemaResult:
        return SchemaResult(entry_id=entry.id, columns=())

    def cancellation_handle(self) -> FakeHandle:
        return FakeHandle(UUID(int=1))


def test_missing_close_fails_protocol_assertion() -> None:
    assert not isinstance(MissingClose(), ExecutionEngine)


def test_base_module_import_does_not_import_streamlit_or_pyspark_or_qt() -> None:
    import subprocess
    import sys

    code = (
        "import sys\n"
        "import wherewolf.execution.base\n"
        "forbidden = ('PyQt6', 'streamlit', 'pyspark')\n"
        "present = [name for name in forbidden if name in sys.modules]\n"
        "if present:\n"
        "    raise SystemExit('forbidden modules loaded')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
