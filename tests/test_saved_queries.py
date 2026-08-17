from pathlib import Path

from wherewolf.storage.saved_queries import SavedQueryStore


def test_saved_query_store_uses_the_user_saved_queries_path_by_default() -> None:
    assert SavedQueryStore.DEFAULT_PATH == Path.home() / ".wherewolf" / "saved_queries.json"
