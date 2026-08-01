import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import polars as pl
import pytest

from wherewolf.domain import CatalogBinding, EngineKind, ExecutionRequest, SourceSnapshot
from wherewolf.domain.enums import SourceFormat
from wherewolf.execution.registry import FULL_XLSX_ROW_LIMIT, _DuckDBAdapter


class _MaterialisationTrap:
    """Connection relation that fails if the streaming path materialises results."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def _called(self, name: str) -> None:
        self.calls.append(name)
        raise AssertionError(f"full export materialised through .{name}()")

    def pl(self):
        self._called("pl")

    def arrow(self):
        self._called("arrow")

    def fetchall(self):
        self._called("fetchall")

    def df(self):
        self._called("df")


class _CopySpyConnection:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.relation = _MaterialisationTrap()

    def execute(self, statement: str) -> None:
        self.statements.append(statement)
        match = re.search(r"TO '((?:''|[^'])*)'", statement)
        assert match is not None
        Path(match.group(1).replace("''", "'")).write_text("streamed")

    def sql(self, _statement: str) -> _MaterialisationTrap:
        return self.relation

    def close(self) -> None:
        pass


def _request(path: Path, limit: int = 2) -> ExecutionRequest:
    stat = path.stat()
    return ExecutionRequest(
        uuid4(),
        EngineKind.DUCKDB,
        "duckdb",
        "SELECT * FROM data",
        "SELECT * FROM data",
        (CatalogBinding(uuid4(), "data", path, SourceFormat.CSV),),
        limit,
        datetime.now(UTC),
        (SourceSnapshot(path, stat.st_size, stat.st_mtime_ns),),
    )


@pytest.mark.parametrize("fmt", ["csv", "parquet"])
def test_full_export_reexecutes_more_than_preview_rows_and_reopens(
    tmp_path: Path, fmt: str
) -> None:
    source = tmp_path / "data.csv"
    pl.DataFrame({"id": range(10)}).write_csv(source)
    destination = tmp_path / f"full.{fmt}"
    _DuckDBAdapter(uuid4()).export_full(_request(source), destination, fmt)
    reopened = pl.read_csv(destination) if fmt == "csv" else pl.read_parquet(destination)
    assert reopened["id"].to_list() == list(range(10))


@pytest.mark.parametrize("fmt", ["csv", "parquet"])
def test_full_export_issues_copy_without_materialising_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fmt: str
) -> None:
    """COPY is the structural streaming contract, not merely an output detail."""
    source = tmp_path / "data.csv"
    pl.DataFrame({"id": range(10)}).write_csv(source)
    connection = _CopySpyConnection()
    adapter = _DuckDBAdapter(uuid4())
    monkeypatch.setattr(adapter, "_register_view", lambda *_args: None)
    import duckdb

    monkeypatch.setattr(duckdb, "connect", lambda **_kwargs: connection)

    adapter.export_full(_request(source, limit=2), tmp_path / f"full.{fmt}", fmt)

    assert len(connection.statements) == 1
    assert connection.statements[0].startswith("COPY (SELECT * FROM data) TO ")
    assert f"FORMAT {fmt.upper()}" in connection.statements[0]
    assert connection.relation.calls == []


def test_full_xlsx_limit_and_source_warning(tmp_path: Path) -> None:
    source = tmp_path / "data.csv"
    pl.DataFrame({"id": range(2)}).write_csv(source)
    request = _request(source)
    source.write_text("id\n1\n2\n3\n")
    warnings = _DuckDBAdapter(uuid4()).export_full(request, tmp_path / "out.csv", "csv")
    assert str(source) in warnings[0]
    pl.DataFrame({"id": range(FULL_XLSX_ROW_LIMIT + 1)}).write_csv(source)
    with pytest.raises(ValueError, match="CSV or Parquet"):
        _DuckDBAdapter(uuid4()).export_full(_request(source, 1), tmp_path / "x.xlsx", "xlsx")
