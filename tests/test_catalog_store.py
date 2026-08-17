import json
from pathlib import Path
from uuid import uuid4

import pytest

from wherewolf.domain import CatalogEntry, SourceFormat


def _entry(path: Path, *, alias: str = "orders") -> CatalogEntry:
    return CatalogEntry(
        id=uuid4(),
        alias=alias,
        path=path,
        source_format=SourceFormat.CSV,
    )


def test_catalog_store_round_trip_preserves_reconstruction_fields(tmp_path: Path) -> None:
    from wherewolf.storage.catalog import CatalogStore

    storage_path = tmp_path / "catalog.json"
    entry = _entry(tmp_path / "orders.csv")

    CatalogStore(storage_path).save((entry,))

    assert CatalogStore(storage_path).load() == (entry,)
    assert json.loads(storage_path.read_text()) == {
        "version": 1,
        "entries": [
            {
                "id": str(entry.id),
                "alias": "orders",
                "path": str(tmp_path / "orders.csv"),
                "source_format": "csv",
            }
        ],
    }


def test_catalog_store_returns_empty_for_corrupt_json(tmp_path: Path) -> None:
    from wherewolf.storage.catalog import CatalogStore

    storage_path = tmp_path / "catalog.json"
    storage_path.write_text("{bad json")

    assert CatalogStore(storage_path).load() == ()


def test_catalog_store_skips_malformed_entry_and_keeps_good_siblings(tmp_path: Path) -> None:
    from wherewolf.storage.catalog import CatalogStore

    entry = _entry(tmp_path / "orders.csv")
    storage_path = tmp_path / "catalog.json"
    storage_path.write_text(
        json.dumps(
            {
                "version": 1,
                "entries": [
                    {
                        "id": str(entry.id),
                        "alias": entry.alias,
                        "path": str(entry.path),
                        "source_format": entry.source_format.value,
                    },
                    {"id": "not-a-uuid", "alias": "broken"},
                ],
            }
        )
    )

    assert CatalogStore(storage_path).load() == (entry,)


def test_catalog_store_interrupted_write_keeps_previous_good_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from wherewolf.storage import catalog
    from wherewolf.storage.catalog import CatalogStore

    storage_path = tmp_path / "catalog.json"
    store = CatalogStore(storage_path)
    original = _entry(tmp_path / "orders.csv")
    store.save((original,))

    monkeypatch.setattr(
        catalog.os, "replace", lambda *_args: (_ for _ in ()).throw(OSError("stop"))
    )

    with pytest.raises(OSError, match="stop"):
        store.save((_entry(tmp_path / "new.csv", alias="new"),))

    assert store.load() == (original,)


def test_catalog_store_loads_legacy_bare_entries_list(tmp_path: Path) -> None:
    from wherewolf.storage.catalog import CatalogStore

    entry = _entry(tmp_path / "orders.csv")
    storage_path = tmp_path / "catalog.json"
    storage_path.write_text(
        json.dumps(
            [
                {
                    "id": str(entry.id),
                    "alias": entry.alias,
                    "path": str(entry.path),
                    "source_format": entry.source_format.value,
                }
            ]
        )
    )

    assert CatalogStore(storage_path).load() == (entry,)
