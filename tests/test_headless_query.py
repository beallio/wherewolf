"""Behavioural contract for the GUI-free DuckDB query runner."""

from __future__ import annotations

import csv
from pathlib import Path
from uuid import UUID

import pytest

from wherewolf.domain import EngineKind, ExecutionRequest
from wherewolf.services.export_destination import ExportFormat
from wherewolf.services.headless_query import (
    HeadlessQueryOptions,
    HeadlessQueryRunner,
    parse_dataset_argument,
)


class _FakeAdapter:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.closed = False
        self.export_calls: list[tuple[ExecutionRequest, Path, str]] = []

    def export_full(
        self, request: ExecutionRequest, destination: Path, export_format: str
    ) -> tuple[str, ...]:
        self.export_calls.append((request, destination, export_format))
        if self.error is not None:
            raise self.error
        destination.write_text("exported")
        return ()

    def close(self) -> None:
        self.closed = True


class _NoExportAdapter:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeRegistry:
    def __init__(self, adapter: object) -> None:
        self.adapter = adapter
        self.calls: list[tuple[EngineKind, UUID]] = []

    def create(self, engine: EngineKind, request_id: UUID) -> object:
        self.calls.append((engine, request_id))
        return self.adapter


def _options(
    sql: str = "SELECT 1 AS answer",
    datasets: tuple[str, ...] = (),
    output: Path = Path("result.csv"),
    *,
    force: bool = False,
    export_format: ExportFormat = ExportFormat.CSV,
) -> HeadlessQueryOptions:
    return HeadlessQueryOptions(
        sql=sql,
        datasets=datasets,
        export_format=export_format,
        output=output,
        force=force,
    )


def _csv_source(tmp_path: Path, name: str = "sales.csv") -> Path:
    source = tmp_path / name
    source.write_text("id,amount\n1,10\n2,20\n")
    return source


def test_dataset_argument_splits_once_and_resolves_a_path_with_equals(tmp_path: Path) -> None:
    source = _csv_source(tmp_path, "with=equals.csv")

    dataset = parse_dataset_argument(f"sales={source}")

    assert dataset.alias == "sales"
    assert dataset.path == source.resolve()


@pytest.mark.parametrize(
    ("argument", "message"),
    (
        ("sales", "Dataset argument must use ALIAS=PATH: 'sales'"),
        ("=sales.csv", "Invalid alias: alias cannot be empty"),
        ("not-valid=sales.csv", "Invalid alias: must be a SQL identifier"),
    ),
)
def test_invalid_dataset_syntax_or_aliases_fail_precisely(
    tmp_path: Path, argument: str, message: str
) -> None:
    if "=" in argument:
        argument = argument.replace("sales.csv", str(_csv_source(tmp_path)))

    with pytest.raises(ValueError, match=message):
        HeadlessQueryRunner().run(_options(datasets=(argument,), output=tmp_path / "out.csv"))


@pytest.mark.parametrize(
    ("source", "message"),
    (
        ("missing.csv", "Dataset file does not exist:"),
        ("directory.csv", "Dataset path is not a file:"),
        ("unsupported.txt", "Unsupported source format for .*: Unsupported source format: .txt"),
    ),
)
def test_dataset_paths_must_be_supported_existing_files(
    tmp_path: Path, source: str, message: str
) -> None:
    path = tmp_path / source
    if source == "directory.csv":
        path.mkdir()
    elif source == "unsupported.txt":
        path.write_text("not a source")

    with pytest.raises(ValueError, match=message):
        HeadlessQueryRunner().run(
            _options(datasets=(f"sales={path}",), output=tmp_path / "out.csv")
        )


def test_duplicate_dataset_aliases_and_paths_fail(tmp_path: Path) -> None:
    source = _csv_source(tmp_path)
    other_source = _csv_source(tmp_path, "other.csv")

    with pytest.raises(ValueError, match="Alias 'sales' already exists"):
        HeadlessQueryRunner().run(
            _options(
                datasets=(f"Sales={source}", f"sales={other_source}"),
                output=tmp_path / "out.csv",
            )
        )

    with pytest.raises(ValueError, match="Duplicate dataset path:"):
        HeadlessQueryRunner().run(
            _options(
                datasets=(f"sales={source}", f"sales_copy={source}"),
                output=tmp_path / "out.csv",
            )
        )


def test_zero_datasets_are_valid_for_a_constant_query(tmp_path: Path) -> None:
    adapter = _FakeAdapter()
    registry = _FakeRegistry(adapter)
    destination = tmp_path / "constant.csv"

    written = HeadlessQueryRunner(engine_registry=registry).run(_options(output=destination))

    request, call_destination, export_format = adapter.export_calls[0]
    assert request.catalog == ()
    assert registry.calls == [(EngineKind.DUCKDB, request.request_id)]
    assert call_destination == destination.resolve()
    assert export_format == "csv"
    assert written == destination.resolve()


def test_existing_destination_fails_closed_without_force(tmp_path: Path) -> None:
    destination = tmp_path / "result.csv"
    destination.write_bytes(b"sentinel")
    adapter = _FakeAdapter()

    with pytest.raises(
        ValueError, match=r"Output file already exists \(use --force to overwrite\):"
    ):
        HeadlessQueryRunner(engine_registry=_FakeRegistry(adapter)).run(
            _options(output=destination)
        )

    assert destination.read_bytes() == b"sentinel"
    assert adapter.export_calls == []


@pytest.mark.parametrize("output_via_symlink", (False, True))
def test_output_cannot_resolve_to_an_input_even_with_force(
    tmp_path: Path, output_via_symlink: bool
) -> None:
    source = _csv_source(tmp_path)
    destination = source
    if output_via_symlink:
        destination = tmp_path / "output-link.csv"
        destination.symlink_to(source)

    with pytest.raises(ValueError, match="Output path must not overwrite an input dataset:"):
        HeadlessQueryRunner().run(
            _options(datasets=(f"sales={source}",), output=destination, force=True)
        )

    assert source.read_text() == "id,amount\n1,10\n2,20\n"


def test_output_directory_fails_without_modification(tmp_path: Path) -> None:
    destination = tmp_path / "output-directory"
    destination.mkdir()

    with pytest.raises(ValueError, match="Output path must not be a directory:"):
        HeadlessQueryRunner().run(_options(output=destination))

    assert destination.is_dir()
    assert list(destination.iterdir()) == []


def test_requested_output_path_is_not_suffix_normalised(tmp_path: Path) -> None:
    adapter = _FakeAdapter()
    destination = tmp_path / "exact-name.not-csv"

    written = HeadlessQueryRunner(engine_registry=_FakeRegistry(adapter)).run(
        _options(output=destination)
    )

    assert adapter.export_calls[0][1] == destination.resolve()
    assert written == destination.resolve()
    assert destination.exists()
    assert not (tmp_path / "exact-name.csv").exists()


@pytest.mark.parametrize("sql", ("", "   ", "SELECT 1; SELECT 2"))
def test_empty_and_multi_statement_sql_fail_before_adapter_creation(
    tmp_path: Path, sql: str
) -> None:
    registry = _FakeRegistry(_FakeAdapter())

    with pytest.raises(ValueError):
        HeadlessQueryRunner(engine_registry=registry).run(
            _options(sql=sql, output=tmp_path / "out.csv")
        )

    assert registry.calls == []


@pytest.mark.parametrize(
    ("sql", "expected"),
    (
        ("SELECT 1 AS value;", "SELECT 1 AS value"),
        ("SELECT 1 AS value; -- trailing comment", "SELECT 1 AS value"),
        ("SELECT ';' AS value;", "SELECT ';' AS value"),
        (
            "SELECT 1 /* semicolon ; remains */ AS value;",
            "SELECT 1 /* semicolon ; remains */ AS value",
        ),
    ),
)
def test_single_statement_trailing_terminator_is_normalised_without_touching_literals_or_comments(
    tmp_path: Path, sql: str, expected: str
) -> None:
    adapter = _FakeAdapter()

    HeadlessQueryRunner(engine_registry=_FakeRegistry(adapter)).run(
        _options(sql=sql, output=tmp_path / "out.csv")
    )

    assert adapter.export_calls[0][0].executable_sql == expected


@pytest.mark.parametrize("export_format", (ExportFormat.CSV, ExportFormat.XLSX))
def test_real_export_accepts_a_trailing_line_comment_after_its_terminator(
    tmp_path: Path, export_format: ExportFormat
) -> None:
    destination = tmp_path / f"trailing-comment.{export_format.value}"

    HeadlessQueryRunner().run(
        _options(
            sql="SELECT 1 AS value; -- trailing comment",
            export_format=export_format,
            output=destination,
        )
    )

    if export_format is ExportFormat.CSV:
        assert destination.read_text() == "value\n1\n"
    else:
        assert destination.read_bytes().startswith(b"PK")


def test_runner_closes_adapter_after_export_failure(tmp_path: Path) -> None:
    adapter = _FakeAdapter(error=RuntimeError("export failed"))

    with pytest.raises(RuntimeError, match="export failed"):
        HeadlessQueryRunner(engine_registry=_FakeRegistry(adapter)).run(
            _options(output=tmp_path / "out.csv")
        )

    assert adapter.closed is True
    assert not (tmp_path / "out.csv").exists()


def test_adapter_without_export_full_fails_explicitly_and_is_closed(tmp_path: Path) -> None:
    adapter = _NoExportAdapter()

    with pytest.raises(TypeError, match="DuckDB adapter does not support full export"):
        HeadlessQueryRunner(engine_registry=_FakeRegistry(adapter)).run(
            _options(output=tmp_path / "out.csv")
        )

    assert adapter.closed is True


def test_real_csv_export_and_non_row_statement_leave_no_partial_destination(tmp_path: Path) -> None:
    source = _csv_source(tmp_path)
    destination = tmp_path / "result.csv"

    HeadlessQueryRunner().run(
        _options(
            sql="SELECT id FROM sales ORDER BY id",
            datasets=(f"sales={source}",),
            output=destination,
        )
    )

    with destination.open(newline="") as handle:
        assert list(csv.DictReader(handle)) == [{"id": "1"}, {"id": "2"}]

    ddl_destination = tmp_path / "ddl.csv"
    with pytest.raises(Exception):  # noqa: B017 - adapter errors vary across supported DuckDB releases.
        HeadlessQueryRunner().run(
            _options(sql="CREATE TABLE created (id INTEGER)", output=ddl_destination)
        )
    assert not ddl_destination.exists()
