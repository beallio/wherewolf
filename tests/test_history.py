from uuid import UUID

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


def test_new_entries_have_versioned_stable_ids_and_streamlit_keys(storage_dir):
    history_file = storage_dir / "history.json"
    manager = HistoryManager(storage_path=history_file)

    manager.add_entry("duckdb", "SELECT * FROM duplicate")
    manager.add_entry("duckdb", "SELECT * FROM duplicate")

    entries = manager.get_all()

    assert len(entries) == 2
    assert {entry["schema_version"] for entry in entries} == {2}
    assert len({entry["id"] for entry in entries}) == 2
    for entry in entries:
        assert UUID(entry["id"]).version == 4
        assert entry["timestamp"][:16]
        assert entry["query"] == "SELECT * FROM duplicate"
