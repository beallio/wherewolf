from pathlib import Path

from PyQt6.QtCore import Qt

from wherewolf.desktop.models import CatalogModel
from wherewolf.domain import ColumnSchema, SchemaResult
from wherewolf.services import CatalogService


def test_catalog_model_tracks_row_and_column_counts() -> None:
    service = CatalogService()
    model = CatalogModel(service)

    assert model.rowCount() == 0
    assert model.columnCount() == 4

    service.add_paths((Path("/tmp/alpha.csv"),))
    assert model.rowCount() == 1


def test_catalog_model_columns_and_tooltip() -> None:
    service = CatalogService()
    model = CatalogModel(service)
    entry = service.add_paths((Path("/tmp/a.csv"),)).added[0]

    assert model.data(model.index(0, 0)) == "a"
    assert model.data(model.index(0, 1)) == str(entry.path)
    assert model.data(model.index(0, 2)) == entry.source_format.value
    assert model.data(model.index(0, 1), Qt.ItemDataRole.ToolTipRole) == str(entry.path)


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

    assert model.data(model.index(0, 3)) == "Ready"
    assert model.data(model.index(1, 3)) == "Error: boom"
    assert model.data(model.index(2, 3)) == "Loading"


def test_catalog_model_emits_model_reset_on_service_change() -> None:
    from PyQt6.QtTest import QSignalSpy

    service = CatalogService()
    model = CatalogModel(service)
    signal_spy = QSignalSpy(model.modelReset)

    service.add_paths((Path("/tmp/reset.csv"),))

    assert len(signal_spy) == 1
    assert model.rowCount() == 1
