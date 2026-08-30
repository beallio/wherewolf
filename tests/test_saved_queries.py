from pathlib import Path

from wherewolf.services import SettingsService

DEFAULT_SAVED_QUERY_DIRECTORY = SettingsService.DEFAULT_SAVED_QUERY_DIRECTORY


def test_saved_query_library_uses_the_user_queries_folder_by_default() -> None:
    assert DEFAULT_SAVED_QUERY_DIRECTORY == Path.home() / ".wherewolf" / "queries"
