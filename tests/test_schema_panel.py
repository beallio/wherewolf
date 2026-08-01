from pathlib import Path
from uuid import uuid4

from pytestqt.qtbot import QtBot

from wherewolf.desktop.widgets.schema_panel import SchemaPanel
from wherewolf.domain.enums import SourceFormat
from wherewolf.domain.models import CatalogEntry, ColumnSchema, SchemaResult


def test_schema_panel_pending_state(qtbot: QtBot) -> None:
    panel = SchemaPanel()
    qtbot.addWidget(panel)

    entry = CatalogEntry(
        id=uuid4(),
        alias="test_table",
        path=Path("test.parquet"),
        source_format=SourceFormat.PARQUET,
        schema=None,
        schema_error=None,
    )
    panel.set_entry(entry)

    # Must show pending state, not an empty table indistinguishable from no columns
    assert panel.is_pending()
    assert "pending" in panel.status_text().lower()


def test_schema_panel_displays_columns_and_types(qtbot: QtBot) -> None:
    panel = SchemaPanel()
    qtbot.addWidget(panel)

    columns = (
        ColumnSchema(name="id", data_type="BIGINT"),
        ColumnSchema(name="user_name", data_type="VARCHAR"),
    )
    entry = CatalogEntry(
        id=uuid4(),
        alias="users",
        path=Path("users.parquet"),
        source_format=SourceFormat.PARQUET,
        schema=columns,
    )
    panel.set_entry(entry)

    assert not panel.is_pending()
    rows = panel.column_count_rows()
    assert rows == 2
    assert panel.cell_text(0, 0) == "id"
    assert panel.cell_text(0, 1) == "BIGINT"
    assert panel.cell_text(1, 0) == "user_name"
    assert panel.cell_text(1, 1) == "VARCHAR"


def test_schema_panel_error_display(qtbot: QtBot) -> None:
    panel = SchemaPanel()
    qtbot.addWidget(panel)

    result = SchemaResult(
        entry_id=uuid4(),
        columns=None,
        error_type="CorruptFileError",
        error_message="Failed to read file footer",
    )
    panel.set_schema_result(result)

    assert panel.has_error()
    assert not panel.is_pending()
    assert "failed to read file footer" in panel.status_text().lower()


def test_schema_panel_entry_schema_error(qtbot: QtBot) -> None:
    panel = SchemaPanel()
    qtbot.addWidget(panel)

    entry = CatalogEntry(
        id=uuid4(),
        alias="corrupt_table",
        path=Path("corrupt.parquet"),
        source_format=SourceFormat.PARQUET,
        schema=None,
        schema_error="Corrupt parquet file header",
    )
    panel.set_entry(entry)

    assert panel.has_error()
    assert not panel.is_pending()
    assert "corrupt parquet file header" in panel.status_text().lower()
