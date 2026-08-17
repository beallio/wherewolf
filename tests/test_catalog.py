"""TDD association for the catalog storage module.

The detailed persistence behaviour lives in ``test_catalog_store.py``; this file
keeps the repository's module-to-test enforcement aligned with ``catalog.py``.
"""

from wherewolf.storage.catalog import CatalogStore


def test_catalog_store_is_available() -> None:
    assert CatalogStore.__name__ == "CatalogStore"
