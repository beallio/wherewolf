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


def test_malformed_records_are_isolated_from_valid_history(storage_dir):
    history_file = storage_dir / "history.json"
    valid_entries = [
        {
            "schema_version": 2,
            "id": "5bb31a12-165e-4a7d-b4f6-439d78c0d50d",
            "timestamp": "2026-08-01T12:00:00+00:00",
            "engine": "duckdb",
            "query": "SELECT retained_one",
            "catalog": {},
        },
        {
            "schema_version": 2,
            "id": "b1c6bb5a-4152-4617-8ec7-dc165d53d5d3",
            "timestamp": "2026-08-01T12:01:00+00:00",
            "engine": "duckdb",
            "query": "SELECT retained_two",
            "catalog": {},
        },
    ]
    storage_dir.mkdir()
    history_file.write_text(json.dumps([valid_entries[0], "corrupt record", valid_entries[1]]))

    entries = HistoryManager(storage_path=history_file).get_all()

    assert len(entries) == 2
    assert [entry["query"] for entry in entries] == [
        "SELECT retained_one",
        "SELECT retained_two",
    ]


def test_unparseable_history_returns_empty_without_deleting_the_file(storage_dir):
    history_file = storage_dir / "history.json"
    broken_content = "[{not valid JSON]"
    storage_dir.mkdir()
    history_file.write_text(broken_content)

    assert HistoryManager(storage_path=history_file).get_all() == []
    assert history_file.exists()
    assert history_file.read_text() == broken_content


def test_record_missing_required_key_is_skipped(storage_dir):
    history_file = storage_dir / "history.json"
    valid_entry = {
        "schema_version": 2,
        "id": "5bb31a12-165e-4a7d-b4f6-439d78c0d50d",
        "timestamp": "2026-08-01T12:00:00+00:00",
        "engine": "duckdb",
        "query": "SELECT retained",
        "catalog": {},
    }
    missing_query = {key: value for key, value in valid_entry.items() if key != "query"}
    storage_dir.mkdir()
    history_file.write_text(json.dumps([valid_entry, missing_query]))

    entries = HistoryManager(storage_path=history_file).get_all()

    assert entries == [valid_entry]


def test_get_by_id_returns_the_matching_record_or_none(storage_dir):
    manager = HistoryManager(storage_path=storage_dir / "history.json")
    manager.add_entry("duckdb", "SELECT first")
    manager.add_entry("duckdb", "SELECT second")
    selected = manager.get_all()[0]

    assert manager.get_by_id(selected["id"]) == selected
    assert manager.get_by_id("f46d098f-4cdc-4ad7-bd40-4c6db2ad0b64") is None


def test_record_cap_evicts_the_oldest_v1_record_after_migration(storage_dir):
    history_file = storage_dir / "history.json"
    v1_entries = [
        {
            "timestamp": f"2026-08-01T12:{index:02d}:00+00:00",
            "engine": "duckdb",
            "query": f"SELECT legacy_{index}",
        }
        for index in range(100)
    ]
    storage_dir.mkdir()
    history_file.write_text(json.dumps(v1_entries))
    manager = HistoryManager(storage_path=history_file)

    assert len(manager.get_all()) == 100
    manager.add_entry("duckdb", "SELECT newest")
    entries = manager.get_all()

    assert len(entries) == 100
    assert entries[0]["query"] == "SELECT newest"
    assert entries[-1]["query"] == "SELECT legacy_98"
    assert "SELECT legacy_99" not in [entry["query"] for entry in entries]


@pytest.mark.parametrize("migrated", [False, True])
def test_history_records_keep_the_exact_streamlit_read_shape(storage_dir, migrated):
    history_file = storage_dir / "history.json"
    if migrated:
        storage_dir.mkdir()
        history_file.write_text(
            json.dumps(
                [
                    {
                        "timestamp": "2026-08-01T12:00:00+00:00",
                        "engine": "duckdb",
                        "query": "SELECT migrated_sql",
                    }
                ]
            )
        )
    manager = HistoryManager(storage_path=history_file)
    if not migrated:
        manager.add_entry("duckdb", "SELECT fresh_sql")

    records = manager.get_all()
    labels = [f"{record['timestamp'][:16]} - {record['query'][:30]}..." for record in records]

    assert len(records[0]["timestamp"][:16]) == 16
    assert labels == [
        f"{records[0]['timestamp'][:16]} - SELECT {'migrated' if migrated else 'fresh'}_sql..."
    ]
    assert records[0]["query"] == f"SELECT {'migrated' if migrated else 'fresh'}_sql"
