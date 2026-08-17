from pathlib import Path
from uuid import uuid4

from PyQt6.QtCore import Qt

from wherewolf.desktop.models import CatalogModel
from wherewolf.domain import CatalogEntry, ColumnSchema, SchemaResult, SourceFormat
from wherewolf.services import CatalogService


def test_catalog_model_tracks_row_and_column_counts() -> None:
    service = CatalogService()
    model = CatalogModel(service)

    assert model.rowCount() == 0
    assert model.columnCount() == 5

    service.add_paths((Path("/tmp/alpha.csv"),))
    assert model.rowCount() == 1


def test_catalog_model_separates_filename_and_folder_columns_with_full_path_tooltips() -> None:
    service = CatalogService()
    model = CatalogModel(service)
    entry = service.add_paths((Path("/tmp/exports/a.csv"),)).added[0]

    assert model.columnCount() == 5
    assert model.data(model.index(0, 0)) == "a"
    assert model.data(model.index(0, 1)) == entry.path.name
    assert "/" not in model.data(model.index(0, 1))
    assert "\\" not in model.data(model.index(0, 1))
    assert model.data(model.index(0, 2)) == str(entry.path.parent)
    assert model.data(model.index(0, 3)) == entry.source_format.value
    assert model.data(model.index(0, 1), Qt.ItemDataRole.ToolTipRole) == str(entry.path)
    assert model.data(model.index(0, 2), Qt.ItemDataRole.ToolTipRole) == str(entry.path)


def test_catalog_model_schema_statuses_and_error_text() -> None:
    service = CatalogService()
    model = CatalogModel(service)
    service.add_paths((Path("/tmp/ready.csv"), Path("/tmp/error.csv"), Path("/tmp/load.csv")))

    ready = service.snapshot()[0]
    error = service.snapshot()[1]

    service.update_schema(
        SchemaResult(
            entry_id=ready.entry_id,
            columns=(ColumnSchema("col", "INT"),),
        )
    )
    service.update_schema(
        SchemaResult(
            entry_id=error.entry_id,
            columns=None,
            error_type="inspect_failed",
            error_message="boom",
        )
    )

    assert model.data(model.index(0, 4)) == "Ready"
    assert model.data(model.index(1, 4)) == "Error: boom"
    assert model.data(model.index(2, 4)) == "Loading"


def test_catalog_model_emits_model_reset_on_service_change() -> None:
    from PyQt6.QtTest import QSignalSpy

    service = CatalogService()
    model = CatalogModel(service)
    signal_spy = QSignalSpy(model.modelReset)

    service.add_paths((Path("/tmp/reset.csv"),))

    assert len(signal_spy) == 1
    assert model.rowCount() == 1


def test_catalog_model_marks_unavailable_entries_with_status_and_foreground() -> None:
    service = CatalogService(
        (
            CatalogEntry(uuid4(), "available", Path("/tmp/available.csv"), SourceFormat.CSV),
            CatalogEntry(
                uuid4(), "missing", Path("/tmp/missing.csv"), SourceFormat.CSV, unavailable=True
            ),
        )
    )
    model = CatalogModel(service)

    assert model.data(model.index(0, 4)) == "Loading"
    assert model.data(model.index(1, 4)) == "Unavailable — file not found"
    assert model.data(model.index(0, 0), Qt.ItemDataRole.ForegroundRole) is None
    assert model.data(model.index(1, 0), Qt.ItemDataRole.ForegroundRole) is not None
