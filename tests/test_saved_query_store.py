import json
from uuid import UUID

import pytest


def test_saved_query_store_round_trip_update_and_delete(tmp_path) -> None:
    from wherewolf.storage.saved_queries import SavedQueryStore

    storage_path = tmp_path / "saved_queries.json"
    store = SavedQueryStore(storage_path)

    saved = store.save_query(
        name="Weekly quality check",
        description="Checks the weekly export.",
        sql="SELECT count(*) FROM {dataset}",
    )

    assert UUID(saved.id).version == 4
    assert store.get_all() == (saved,)
    assert store.get_by_id(saved.id) == saved

    updated = store.update_query(
        saved.id,
        name="Weekly data quality check",
        description="Checks the current weekly export.",
    )

    assert updated is not None
    assert updated.name == "Weekly data quality check"
    assert updated.description == "Checks the current weekly export."
    assert updated.sql == "SELECT count(*) FROM {dataset}"
    assert updated.created_at == saved.created_at
    assert updated.updated_at >= saved.updated_at
    assert store.delete_query(saved.id)
    assert store.get_all() == ()
    assert not store.delete_query(saved.id)


def test_saved_query_store_rejects_duplicate_names(tmp_path) -> None:
    from wherewolf.storage.saved_queries import SavedQueryStore

    store = SavedQueryStore(tmp_path / "saved_queries.json")
    store.save_query(name="Daily check", description="", sql="SELECT 1")

    with pytest.raises(ValueError, match="already exists"):
        store.save_query(name="Daily check", description="", sql="SELECT 2")


def test_saved_query_store_loads_corrupt_file_as_empty(tmp_path) -> None:
    from wherewolf.storage.saved_queries import SavedQueryStore

    storage_path = tmp_path / "saved_queries.json"
    storage_path.write_text("{bad json", encoding="utf-8")

    assert SavedQueryStore(storage_path).get_all() == ()


def test_saved_query_store_skips_malformed_records(tmp_path) -> None:
    from wherewolf.storage.saved_queries import SavedQueryStore

    storage_path = tmp_path / "saved_queries.json"
    storage_path.write_text(
        json.dumps(
            {
                "version": 1,
                "queries": [
                    {
                        "id": "5bb31a12-165e-4a7d-b4f6-439d78c0d50d",
                        "name": "Valid",
                        "description": "",
                        "sql": "SELECT 1",
                        "created_at": "2026-08-17T12:00:00+00:00",
                        "updated_at": "2026-08-17T12:00:00+00:00",
                    },
                    {"id": "not-a-uuid", "name": "Broken"},
                ],
            }
        ),
        encoding="utf-8",
    )

    queries = SavedQueryStore(storage_path).get_all()

    assert [query.name for query in queries] == ["Valid"]


def test_saved_query_store_interrupted_write_keeps_previous_file(tmp_path, monkeypatch) -> None:
    from wherewolf.storage import saved_queries
    from wherewolf.storage.saved_queries import SavedQueryStore

    storage_path = tmp_path / "saved_queries.json"
    store = SavedQueryStore(storage_path)
    original = store.save_query(name="Original", description="", sql="SELECT 1")

    monkeypatch.setattr(
        saved_queries.os, "replace", lambda *_args: (_ for _ in ()).throw(OSError("stop"))
    )

    with pytest.raises(OSError, match="stop"):
        store.save_query(name="Replacement", description="", sql="SELECT 2")

    assert store.get_all() == (original,)
