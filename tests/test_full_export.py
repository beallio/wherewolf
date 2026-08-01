from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import polars as pl
import pytest

from wherewolf.domain import CatalogBinding, EngineKind, ExecutionRequest, SourceSnapshot
from wherewolf.domain.enums import SourceFormat
from wherewolf.execution.registry import FULL_XLSX_ROW_LIMIT, _DuckDBAdapter


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
