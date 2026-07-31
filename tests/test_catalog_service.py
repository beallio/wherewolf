from pathlib import Path

import polars as pl
import pytest

from wherewolf.domain import ColumnSchema, SchemaResult
from wherewolf.services.catalog_service import CatalogService


def _write_csv(path: Path) -> None:
    pl.DataFrame({"a": [1]}).write_csv(path)


def test_add_paths_resolves_before_duplicate_check(tmp_path: Path) -> None:
    service = CatalogService()
    real = tmp_path / "a.csv"
    _write_csv(real)
    symlink = tmp_path / "a_link.csv"
    symlink.symlink_to(real)

    result = service.add_paths((symlink, real))

    assert len(result.added) == 1
    assert result.duplicates == (symlink.resolve(),)


def test_add_paths_duplicate_resolved_path_in_same_call_is_a_single_entry(tmp_path: Path) -> None:
    service = CatalogService()
    path = tmp_path / "dup.csv"
    _write_csv(path)

    first = service.add_paths((path, path))
    assert len(first.added) == 1
    assert len(first.duplicates) == 1

    assert len(service.snapshot()) == 1


def test_add_paths_generates_valid_sql_identifier_alias(tmp_path: Path) -> None:
    service = CatalogService()
    weird_path = tmp_path / "Weird Name!.csv"
    _write_csv(weird_path)
    service.add_paths((weird_path,))

    assert service.snapshot()[0].alias == "weird_name"


def test_add_paths_alias_collisions_are_deterministic(tmp_path: Path) -> None:
    service = CatalogService()
    path_primary = tmp_path / "orders.csv"
    path_secondary = tmp_path / "orders .csv"
    path_tertiary = tmp_path / "orders--.csv"
    _write_csv(path_primary)
    _write_csv(path_secondary)
    _write_csv(path_tertiary)
    service.add_paths(
        (
            path_primary,
            path_secondary,
            path_tertiary,
        )
    )

    aliases = [entry.alias for entry in service.snapshot()]
    assert aliases == ["orders", "orders_2", "orders_3"]


def test_add_paths_alias_uniqueness_is_casefold(tmp_path: Path) -> None:
    service = CatalogService()
    first_path = tmp_path / "Orders.csv"
    second_path = tmp_path / "orders.csv"
    _write_csv(first_path)
    _write_csv(second_path)
    first_entry = service.add_paths((first_path,)).added[0]
    service.rename(first_entry.id, first_entry.alias.upper())

    result = service.add_paths((second_path,))

    assert len(result.added) == 1
    assert result.added[0].alias == "orders_2"


def test_add_paths_reports_unsupported_extension_and_keeps_supported(tmp_path: Path) -> None:
    service = CatalogService()
    supported = tmp_path / "good.csv"
    unsupported = tmp_path / "bad.xls"
    unsupported.write_text("a\n1")
    _write_csv(supported)

    result = service.add_paths((unsupported, supported))

    assert len(result.added) == 1
    assert result.added[0].path == supported.resolve()
    assert len(result.warnings) == 1
    assert "Unsupported source format" in result.warnings[0]


def test_rename_rejects_invalid_alias_preserves_entry(tmp_path: Path) -> None:
    service = CatalogService()
    path = tmp_path / "alias.csv"
    _write_csv(path)
    entry = service.add_paths((path,)).added[0]

    with pytest.raises(ValueError, match="Invalid alias"):
        service.rename(entry.id, "")

    assert service.snapshot()[0].alias == entry.alias


def test_rename_rejects_casefold_collision(tmp_path: Path) -> None:
    service = CatalogService()
    a_path = tmp_path / "a.csv"
    b_path = tmp_path / "b.csv"
    _write_csv(a_path)
    _write_csv(b_path)
    first = service.add_paths((a_path, b_path)).added[0]
    target_alias = f"{service.snapshot()[1].alias.upper()}"

    with pytest.raises(ValueError, match="already exists"):
        service.rename(first.id, target_alias)


def test_remove_by_entry_id(tmp_path: Path) -> None:
    service = CatalogService()
    entry_id = service.add_paths((tmp_path / "remove.csv",)).added[0].id
    tmp_path.joinpath("remove.csv").write_text("a\n1")

    assert service.remove(entry_id) is True
    assert service.snapshot() == ()
    assert service.remove(entry_id) is False


def test_update_schema_success_and_error_do_not_store_empty_tuple(tmp_path: Path) -> None:
    service = CatalogService()
    entry = service.add_paths((tmp_path / "schema.csv",)).added[0]
    tmp_path.joinpath("schema.csv").write_text("a,b\n1,2")

    service.update_schema(SchemaResult(entry_id=entry.id, columns=(ColumnSchema("a", "INTEGER"),)))
    assert service.snapshot()[0] is not None

    service.update_schema(
        SchemaResult(
            entry_id=entry.id,
            columns=None,
            error_type="inspect_failed",
            error_message="bad schema",
        )
    )
    current = service.entries[0]
    assert current.schema is None
    assert current.schema_error == "bad schema"


def test_snapshot_is_not_mutated_by_later_service_updates(tmp_path: Path) -> None:
    service = CatalogService()
    first = service.add_paths((tmp_path / "first.csv",)).added[0]
    tmp_path.joinpath("first.csv").write_text("a\n1")
    snapshot = service.snapshot()

    second_path = tmp_path / "second.csv"
    _write_csv(second_path)
    service.add_paths((second_path,))

    assert len(snapshot) == 1
    assert snapshot[0].entry_id == first.id
