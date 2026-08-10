from pathlib import Path
from uuid import uuid4

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from wherewolf.desktop.widgets.schema_panel import SchemaPanel
from wherewolf.domain.enums import SourceFormat
from wherewolf.domain.models import (
    CatalogEntry,
    ColumnProfile,
    ColumnSchema,
    ProfileResult,
    SchemaResult,
)


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


def test_schema_panel_displays_nullable_state_and_ordinal(qtbot: QtBot) -> None:
    panel = SchemaPanel()
    qtbot.addWidget(panel)
    entry = CatalogEntry(
        id=uuid4(),
        alias="users",
        path=Path("users.parquet"),
        source_format=SourceFormat.PARQUET,
        schema=(
            ColumnSchema("allows_null", "VARCHAR", True),
            ColumnSchema("required", "BIGINT", False),
            ColumnSchema("unknown", "BOOLEAN", None),
        ),
    )
    panel.set_entry(entry)

    assert [panel.cell_text(row, 2) for row in range(3)] == ["Yes", "No", "Unknown"]
    assert [panel.cell_text(row, 3) for row in range(3)] == ["1", "2", "3"]
    assert "users.parquet" in panel.status_text()


def test_schema_panel_displays_profile_with_approximate_distinct_label(qtbot: QtBot) -> None:
    panel = SchemaPanel()
    qtbot.addWidget(panel)
    entry_id = uuid4()
    panel.set_entry(
        CatalogEntry(
            id=entry_id,
            alias="users",
            path=Path("users.csv"),
            source_format=SourceFormat.CSV,
            schema=(ColumnSchema("category", "VARCHAR"),),
        )
    )
    panel.set_profile_result(
        ProfileResult(
            entry_id=entry_id,
            profiles=(
                ColumnProfile(
                    "category", "VARCHAR", "a", "z", 2, None, None, None, None, None, 2, 0.0
                ),
            ),
        )
    )

    header = panel._table_widget.horizontalHeaderItem(5)
    assert header is not None
    assert "Distinct (approx.)" in header.text()
    assert panel.cell_text(0, 4) == "0.00"
    assert panel.cell_text(0, 5) == "2"
    assert panel.cell_text(0, 8) == ""


def test_schema_panel_displays_temporal_profile_mean_verbatim(qtbot: QtBot) -> None:
    panel = SchemaPanel()
    qtbot.addWidget(panel)
    entry_id = uuid4()
    panel.set_entry(
        CatalogEntry(
            id=entry_id,
            alias="events",
            path=Path("events.csv"),
            source_format=SourceFormat.CSV,
            schema=(ColumnSchema("event_ts", "TIMESTAMP"),),
        )
    )
    panel.set_profile_result(
        ProfileResult(
            entry_id=entry_id,
            profiles=(
                ColumnProfile(
                    "event_ts",
                    "TIMESTAMP",
                    "2024-01-01 00:00:00",
                    "2024-01-01 00:01:39",
                    100,
                    "2024-01-01 00:00:49.5",
                    None,
                    None,
                    None,
                    None,
                    100,
                    0.0,
                ),
            ),
        )
    )

    assert panel.cell_text(0, 8) == "2024-01-01 00:00:49.5"


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


def test_schema_panel_insert_columns_single(qtbot: QtBot) -> None:
    panel = SchemaPanel()
    qtbot.addWidget(panel)

    columns = (
        ColumnSchema(name="user_id", data_type="BIGINT"),
        ColumnSchema(name="first name", data_type="VARCHAR"),
    )
    entry = CatalogEntry(
        id=uuid4(),
        alias="users",
        path=Path("users.parquet"),
        source_format=SourceFormat.PARQUET,
        schema=columns,
    )
    panel.set_entry(entry)

    received: list[str] = []
    panel.insert_columns_requested.connect(received.append)

    # Select second row ("first name")
    panel._table_widget.selectRow(1)
    panel.emit_selected_columns_insert()

    assert len(received) == 1
    assert received[0] == '"first name"'


from PyQt6.QtWidgets import QTableWidgetSelectionRange


def test_schema_panel_insert_columns_multi_display_order(qtbot: QtBot) -> None:
    panel = SchemaPanel()
    qtbot.addWidget(panel)

    columns = (
        ColumnSchema(name="user_id", data_type="BIGINT"),
        ColumnSchema(name="first name", data_type="VARCHAR"),
        ColumnSchema(name="select", data_type="BOOLEAN"),
    )
    entry = CatalogEntry(
        id=uuid4(),
        alias="users",
        path=Path("users.parquet"),
        source_format=SourceFormat.PARQUET,
        schema=columns,
    )
    panel.set_entry(entry)

    received: list[str] = []
    panel.insert_columns_requested.connect(received.append)

    # Select row 2 and row 0 (multi-selection via ranges)
    panel._table_widget.setRangeSelected(QTableWidgetSelectionRange(2, 0, 2, 1), True)
    panel._table_widget.setRangeSelected(QTableWidgetSelectionRange(0, 0, 0, 1), True)
    panel.emit_selected_columns_insert()

    assert len(received) == 1
    # Must be in display order (row 0: user_id, row 2: "select")
    assert received[0] == 'user_id, "select"'


def test_schema_panel_ctrl_c_copies_selected_rows_as_tsv(qtbot: QtBot) -> None:
    panel = SchemaPanel()
    qtbot.addWidget(panel)
    panel.set_entry(
        CatalogEntry(
            id=uuid4(),
            alias="users",
            path=Path("users.parquet"),
            source_format=SourceFormat.PARQUET,
            schema=(ColumnSchema("id", "BIGINT"), ColumnSchema("name", "VARCHAR")),
        )
    )
    panel._table_widget.selectRow(0)
    panel._table_widget.setFocus()
    qtbot.keyClick(panel._table_widget, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)

    clipboard = QApplication.clipboard()
    assert clipboard is not None
    assert clipboard.text() == "id\tBIGINT\tUnknown\t1\t\t\t\t\t"


def test_schema_panel_context_menu_copy_matches_keyboard_copy(qtbot: QtBot) -> None:
    panel = SchemaPanel()
    qtbot.addWidget(panel)
    panel.set_entry(
        CatalogEntry(
            id=uuid4(),
            alias="users",
            path=Path("users.parquet"),
            source_format=SourceFormat.PARQUET,
            schema=(ColumnSchema("id", "BIGINT"),),
        )
    )
    panel._table_widget.selectRow(0)
    panel.copy_selection()
    clipboard = QApplication.clipboard()
    assert clipboard is not None
    keyboard_text = clipboard.text()

    action = next(
        action for action in panel.create_context_menu().actions() if action.text() == "Copy"
    )
    action.trigger()

    assert clipboard.text() == keyboard_text


def test_schema_panel_copy_with_empty_selection_does_nothing(qtbot: QtBot) -> None:
    panel = SchemaPanel()
    qtbot.addWidget(panel)
    clipboard = QApplication.clipboard()
    assert clipboard is not None
    clipboard.setText("keep me")

    panel.copy_selection()

    assert clipboard.text() == "keep me"


def test_schema_panel_value_counts_context_action_emits_entry_and_column(qtbot: QtBot) -> None:
    panel = SchemaPanel()
    qtbot.addWidget(panel)
    entry = CatalogEntry(
        id=uuid4(),
        alias="users",
        path=Path("users.parquet"),
        source_format=SourceFormat.PARQUET,
        schema=(ColumnSchema("category", "VARCHAR"),),
    )
    panel.set_entry(entry)

    with qtbot.waitSignal(panel.value_counts_requested) as signal:
        panel.create_context_menu(0, 0).actions()[-1].trigger()

    assert signal.args == [entry, "category"]
