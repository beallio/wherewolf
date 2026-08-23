"""DuckDB-only query-to-file execution that never imports the desktop stack."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast
from uuid import UUID

from wherewolf.domain import EngineKind
from wherewolf.execution.registry import EngineRegistry
from wherewolf.services.catalog_service import CatalogService
from wherewolf.services.execution_request_builder import ExecutionRequestBuilder
from wherewolf.services.export_destination import ExportFormat
from wherewolf.services.statement_service import StatementService


@dataclass(frozen=True, slots=True)
class HeadlessQueryOptions:
    """Inputs accepted by the ``wherewolf query`` command."""

    sql: str
    datasets: tuple[str, ...]
    export_format: ExportFormat
    output: Path
    force: bool = False


@dataclass(frozen=True, slots=True)
class DatasetArgument:
    """A dataset alias paired with a canonical on-disk source path."""

    alias: str
    path: Path


class _ClosableAdapter(Protocol):
    def close(self) -> None: ...


class _EngineRegistry(Protocol):
    def create(self, engine: EngineKind, request_id: UUID) -> _ClosableAdapter: ...


def parse_dataset_argument(raw: str) -> DatasetArgument:
    """Parse one ``ALIAS=PATH`` argument without treating later equals signs specially."""
    if "=" not in raw:
        raise ValueError(f"Dataset argument must use ALIAS=PATH: {raw!r}")
    alias, raw_path = raw.split("=", 1)
    return DatasetArgument(alias=alias, path=Path(raw_path).expanduser().resolve())


class HeadlessQueryRunner:
    """Build a request-scoped DuckDB export without touching Qt or PySpark."""

    def __init__(self, engine_registry: object | None = None) -> None:
        self._engine_registry = cast(_EngineRegistry, engine_registry or EngineRegistry())

    def run(self, options: HeadlessQueryOptions) -> Path:
        """Export one validated SQL statement and return its absolute destination."""
        datasets = tuple(parse_dataset_argument(raw) for raw in options.datasets)
        catalog = self._catalog_for(datasets)
        destination = self._validated_destination(options, datasets)
        sql = _normalise_single_statement(options.sql)
        request = ExecutionRequestBuilder.build(
            sql=sql,
            source_dialect=EngineKind.DUCKDB.value,
            engine=EngineKind.DUCKDB,
            catalog_service=catalog,
        )

        adapter = self._engine_registry.create(EngineKind.DUCKDB, request.request_id)
        try:
            export_full = getattr(adapter, "export_full", None)
            if not callable(export_full):
                raise TypeError("DuckDB adapter does not support full export")
            export_full(request, destination, options.export_format.value)
        finally:
            adapter.close()
        return destination

    @staticmethod
    def _catalog_for(datasets: tuple[DatasetArgument, ...]) -> CatalogService:
        catalog = CatalogService()
        for dataset in datasets:
            if not dataset.path.exists():
                raise ValueError(f"Dataset file does not exist: {dataset.path}")
            if not dataset.path.is_file():
                raise ValueError(f"Dataset path is not a file: {dataset.path}")

            report = catalog.add_paths((dataset.path,))
            if report.warnings:
                raise ValueError(report.warnings[0])
            if report.duplicates:
                raise ValueError(f"Duplicate dataset path: {dataset.path}")
            if len(report.added) != 1:
                raise RuntimeError(f"Could not add dataset: {dataset.path}")
            catalog.rename(report.added[0].id, dataset.alias)
        return catalog

    @staticmethod
    def _validated_destination(
        options: HeadlessQueryOptions, datasets: tuple[DatasetArgument, ...]
    ) -> Path:
        destination = options.output.expanduser().resolve()
        if destination.is_dir():
            raise ValueError(f"Output path must not be a directory: {destination}")
        if destination in {dataset.path for dataset in datasets}:
            raise ValueError(f"Output path must not overwrite an input dataset: {destination}")
        if destination.exists() and not options.force:
            raise ValueError(
                f"Output file already exists (use --force to overwrite): {destination}"
            )
        return destination


def _normalise_single_statement(sql: str) -> str:
    statements = StatementService().split_statements(sql)
    if not statements:
        raise ValueError("SQL statement cannot be empty")
    if len(statements) != 1:
        raise ValueError("SQL must contain exactly one executable statement")

    statement = statements[0]
    semicolon_offset = statement.end_offset - 1
    if sql[semicolon_offset : statement.end_offset] == ";":
        sql = f"{sql[:semicolon_offset]}{sql[statement.end_offset :]}"
    normalised = sql.strip()
    if not normalised:
        raise ValueError("SQL statement cannot be empty")
    return normalised


__all__ = [
    "DatasetArgument",
    "HeadlessQueryOptions",
    "HeadlessQueryRunner",
    "parse_dataset_argument",
]
