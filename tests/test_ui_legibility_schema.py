from pathlib import Path

from wherewolf.desktop.main_window import MainWindow
from wherewolf.domain import SchemaResult
from wherewolf.domain.models import ColumnSchema


def test_main_window_schema_panel_names_the_current_dataset(tmp_path: Path, qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    columns = (ColumnSchema(name="id", data_type="BIGINT"),)

    for alias in ("customers", "loans"):
        dataset = tmp_path / f"{alias}.csv"
        dataset.write_text("id\n1\n")
        entry = window._catalog_service.add_paths((dataset,)).added[0]
        window._on_schema_result(SchemaResult(entry_id=entry.id, columns=columns))

        assert alias in window.schema_panel.status_text()


def test_main_window_tables_use_legible_alternating_rows(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    views = (
        window.history_dock.history_table,
        window.catalog.view,
        window.schema_panel._table_widget,
    )
    for view in views:
        assert view.alternatingRowColors()
        palette = view.palette()
        alternate = palette.alternateBase().color()
        text = palette.text().color()
        alternate_luminance = (
            (0.2126 * alternate.red()) + (0.7152 * alternate.green()) + (0.0722 * alternate.blue())
        )
        text_luminance = (0.2126 * text.red()) + (0.7152 * text.green()) + (0.0722 * text.blue())
        assert abs(alternate_luminance - text_luminance) >= 20
