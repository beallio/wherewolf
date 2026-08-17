from pathlib import Path

from wherewolf.storage.saved_queries import SavedQueryStore

DEFAULT_SAVED_QUERY_PATH = SavedQueryStore.DEFAULT_PATH


def test_saved_query_store_uses_the_user_saved_queries_path_by_default() -> None:
    assert DEFAULT_SAVED_QUERY_PATH == Path.home() / ".wherewolf" / "saved_queries.json"
