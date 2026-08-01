import json
from unittest.mock import patch
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


def test_v1_history_migrates_all_records_in_order_and_only_once(storage_dir):
    history_file = storage_dir / "history.json"
    v1_entries = [
        {
            "timestamp": f"2026-08-01T12:{index:02d}:00+00:00",
            "engine": "duckdb",
            "query": f"SELECT {index}",
            "path": "",
        }
        for index in range(100)
    ]
    storage_dir.mkdir()
    history_file.write_text(json.dumps(v1_entries))

    manager = HistoryManager(storage_path=history_file)
    migrated = manager.get_all()

    assert [entry["query"] for entry in migrated] == [entry["query"] for entry in v1_entries]
    assert len(migrated) == 100
    assert all(entry["schema_version"] == 2 for entry in migrated)
    assert len({entry["id"] for entry in migrated}) == 100

    first_persisted_content = history_file.read_text()
    assert manager.get_all() == migrated
    assert history_file.read_text() == first_persisted_content


def test_existing_v2_history_is_not_rewritten(storage_dir):
    history_file = storage_dir / "history.json"
    v2_entries = [
        {
            "schema_version": 2,
            "id": "5bb31a12-165e-4a7d-b4f6-439d78c0d50d",
            "timestamp": "2026-08-01T12:00:00+00:00",
            "engine": "duckdb",
            "query": "SELECT 1",
            "path": "",
            "catalog": {},
        }
    ]
    storage_dir.mkdir()
    history_file.write_text(json.dumps(v2_entries))

    manager = HistoryManager(storage_path=history_file)

    assert manager.get_all() == v2_entries
    assert json.loads(history_file.read_text()) == v2_entries


def test_failed_migration_leaves_the_original_v1_file_intact(storage_dir):
    history_file = storage_dir / "history.json"
    v1_entries = [
        {"timestamp": "2026-08-01T12:00:00+00:00", "engine": "duckdb", "query": "SELECT 1"}
    ]
    storage_dir.mkdir()
    history_file.write_text(json.dumps(v1_entries))

    manager = HistoryManager(storage_path=history_file)
    with (
        patch.object(manager, "_write_history", side_effect=OSError("Disk full")),
        pytest.raises(OSError, match="Disk full"),
    ):
        manager.get_all()

    assert json.loads(history_file.read_text()) == v1_entries
