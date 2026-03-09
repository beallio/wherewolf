import pytest
from wherewolf.storage import HistoryManager


@pytest.fixture
def storage_dir(tmp_path):
    return tmp_path / ".wherewolf"


def test_history_manager_add_and_get(storage_dir):
    history_file = storage_dir / "history.json"
    manager = HistoryManager(storage_path=history_file)

    manager.add_entry("duckdb", "SELECT * FROM dataset", "/tmp/test.csv")
    entries = manager.get_all()

    assert len(entries) == 1
    assert entries[0]["engine"] == "duckdb"
    assert entries[0]["query"] == "SELECT * FROM dataset"
    assert "timestamp" in entries[0]


def test_history_manager_persistence(storage_dir):
    history_file = storage_dir / "history.json"
    manager1 = HistoryManager(storage_path=history_file)
    manager1.add_entry("spark", "SELECT 1", "/tmp/test.parquet")

    # New manager instance should load same data
    manager2 = HistoryManager(storage_path=history_file)
    entries = manager2.get_all()

    assert len(entries) == 1
    assert entries[0]["engine"] == "spark"


def test_history_manager_clear(storage_dir):
    history_file = storage_dir / "history.json"
    manager = HistoryManager(storage_path=history_file)
    manager.add_entry("duckdb", "Q1", "P1")
    manager.clear()

    assert len(manager.get_all()) == 0
