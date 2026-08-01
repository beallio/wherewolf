from pathlib import Path

import polars as pl

from wherewolf.desktop.main_window import MainWindow
from wherewolf.services import CatalogService
from wherewolf.storage.history import HistoryManager


def test_end_to_end_desktop_duckdb_execution_and_history(tmp_path: Path, qtbot) -> None:
    # 1. Setup sample CSV and Parquet files
    csv_path = tmp_path / "orders.csv"
    csv_path.write_text("order_id,amount\n101,50.5\n102,99.9\n")

    df_customers = pl.DataFrame({"cust_id": [1, 2], "name": ["Alice", "Bob"]})
    parquet_path = tmp_path / "customers.parquet"
    df_customers.write_parquet(parquet_path)

    catalog_service = CatalogService()
    history_file = tmp_path / "history.json"
    history_manager = HistoryManager(storage_path=history_file)

    window = MainWindow(
        catalog_service=catalog_service,
        history_manager=history_manager,
    )
    qtbot.addWidget(window)
    window.show()

    # 2. Add files to catalog
    catalog_service.add_paths((csv_path, parquet_path))

    # 3. Enter multi-table SQL query into editor referencing catalog aliases
    query_sql = "SELECT o.order_id, c.name, o.amount FROM orders AS o CROSS JOIN customers AS c ORDER BY o.order_id, c.name"
    window.editor.setText(query_sql)
    window.editor.selectAll()

    # 4. Trigger Run action and wait for execution completion
    with qtbot.waitSignal(window.query_controller.result_ready, timeout=5000) as blocker:
        window.desktop_actions.run.trigger()

    result = blocker.args[0]
    assert result.status.name == "SUCCEEDED"
    assert result.frame is not None
    assert result.frame.shape == (4, 3)
    assert result.frame.columns == ["order_id", "name", "amount"]

    # 5. Check status bar message
    msg = window.status_bar.currentMessage()
    assert "DuckDB" in msg
    assert "Succeeded" in msg
    assert "Preview Rows: 4" in msg

    # 6. Verify History persistence append
    history_entries = history_manager.get_all()
    assert len(history_entries) == 1
    entry = history_entries[0]
    assert entry["engine"] == "duckdb"
    assert entry["query"] == query_sql
    assert "orders" in entry["catalog"]
    assert "customers" in entry["catalog"]
