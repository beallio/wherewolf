import pytest


def test_saved_query_directory_scans_recursively_and_derives_names(tmp_path) -> None:
    from wherewolf.storage.saved_queries import SavedQueryDirectory

    root = tmp_path / "queries"
    (root / "reports").mkdir(parents=True)
    (root / "daily check.sql").write_text("SELECT 1", encoding="utf-8")
    (root / "reports" / "weekly.SQL").write_text("SELECT 2", encoding="utf-8")
    (root / "notes.txt").write_text("not a query", encoding="utf-8")

    queries = SavedQueryDirectory(root).get_all()

    assert [query.name for query in queries] == ["daily check", "reports/weekly"]
    assert [query.sql for query in queries] == ["SELECT 1", "SELECT 2"]
    assert queries[1].id == str(root / "reports" / "weekly.SQL")
    assert queries[0].updated_at.endswith("+00:00")


def test_saved_query_directory_skips_hidden_and_unreadable_files(tmp_path) -> None:
    from wherewolf.storage.saved_queries import SavedQueryDirectory

    root = tmp_path / "queries"
    (root / ".trash").mkdir(parents=True)
    (root / "keep.sql").write_text("SELECT 1", encoding="utf-8")
    (root / ".trash" / "dropped.sql").write_text("SELECT 2", encoding="utf-8")
    (root / ".hidden.sql").write_text("SELECT 3", encoding="utf-8")
    (root / "undecodable.sql").write_bytes(b"SELECT '\xff\xfe'")

    assert [query.name for query in SavedQueryDirectory(root).get_all()] == ["keep"]


def test_saved_query_directory_reads_missing_root_as_empty(tmp_path) -> None:
    from wherewolf.storage.saved_queries import SavedQueryDirectory

    library = SavedQueryDirectory(tmp_path / "absent")

    assert library.get_all() == ()

    library.set_directory(tmp_path / "present")
    (tmp_path / "present").mkdir()
    (tmp_path / "present" / "one.sql").write_text("SELECT 1", encoding="utf-8")

    assert [query.name for query in library.get_all()] == ["one"]


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        ("-- Weekly rollup\n-- Counts rows.\nSELECT 1", "Weekly rollup\nCounts rows."),
        ("\n\n--Leading blanks\nSELECT 1", "Leading blanks"),
        ("/* Block form\n   second line */\nSELECT 1", "Block form\nsecond line"),
        ("SELECT 1 -- trailing only", ""),
        ("-- first\nSELECT 1\n-- second\n", "first"),
        ("", ""),
    ],
)
def test_extract_description_reads_the_leading_comment(sql: str, expected: str) -> None:
    from wherewolf.storage.saved_queries import extract_description

    assert extract_description(sql) == expected


def test_saved_query_directory_exposes_the_leading_comment_as_description(tmp_path) -> None:
    from wherewolf.storage.saved_queries import SavedQueryDirectory

    root = tmp_path / "queries"
    root.mkdir()
    (root / "documented.sql").write_text("-- Counts the export.\nSELECT 1", encoding="utf-8")

    query = SavedQueryDirectory(root).get_all()[0]

    assert query.description == "Counts the export."


def test_saved_query_directory_saves_into_subfolders(tmp_path) -> None:
    from wherewolf.storage.saved_queries import SavedQueryDirectory

    root = tmp_path / "queries"
    library = SavedQueryDirectory(root)

    saved = library.save_query(name="reports/weekly", sql="-- Weekly\nSELECT 1")

    assert (root / "reports" / "weekly.sql").read_text(encoding="utf-8") == "-- Weekly\nSELECT 1"
    assert saved.name == "reports/weekly"
    assert saved.description == "Weekly"
    assert library.get_all() == (saved,)


def test_saved_query_directory_rejects_a_name_that_already_exists(tmp_path) -> None:
    from wherewolf.storage.saved_queries import SavedQueryDirectory

    library = SavedQueryDirectory(tmp_path / "queries")
    library.save_query(name="daily", sql="SELECT 1")

    with pytest.raises(ValueError, match="already exists"):
        library.save_query(name="daily", sql="SELECT 2")


@pytest.mark.parametrize(
    "name",
    [
        "",
        "   ",
        "/absolute",
        "../escape",
        "reports/../../escape",
        "back\\slash",
        "trailing.",
        "reports /weekly",
    ],
)
def test_saved_query_directory_rejects_unusable_names(tmp_path, name: str) -> None:
    from wherewolf.storage.saved_queries import SavedQueryDirectory

    library = SavedQueryDirectory(tmp_path / "queries")

    with pytest.raises(ValueError):
        library.save_query(name=name, sql="SELECT 1")

    assert library.get_all() == ()


def test_saved_query_directory_trims_surrounding_whitespace_from_a_name(tmp_path) -> None:
    from wherewolf.storage.saved_queries import SavedQueryDirectory

    library = SavedQueryDirectory(tmp_path / "queries")

    saved = library.save_query(name="  daily check  ", sql="SELECT 1")

    assert saved.name == "daily check"
    assert (tmp_path / "queries" / "daily check.sql").is_file()


def test_saved_query_directory_renames_across_subfolders(tmp_path) -> None:
    from wherewolf.storage.saved_queries import SavedQueryDirectory

    root = tmp_path / "queries"
    library = SavedQueryDirectory(root)
    saved = library.save_query(name="draft", sql="SELECT 1")

    renamed = library.rename_query(saved.id, "reports/final")

    assert renamed is not None
    assert renamed.name == "reports/final"
    assert not (root / "draft.sql").exists()
    assert (root / "reports" / "final.sql").read_text(encoding="utf-8") == "SELECT 1"
    assert library.rename_query(str(root / "gone.sql"), "whatever") is None


def test_saved_query_directory_rename_refuses_to_clobber(tmp_path) -> None:
    from wherewolf.storage.saved_queries import SavedQueryDirectory

    root = tmp_path / "queries"
    library = SavedQueryDirectory(root)
    first = library.save_query(name="first", sql="SELECT 1")
    library.save_query(name="second", sql="SELECT 2")

    with pytest.raises(ValueError, match="already exists"):
        library.rename_query(first.id, "second")

    assert (root / "first.sql").read_text(encoding="utf-8") == "SELECT 1"
    assert (root / "second.sql").read_text(encoding="utf-8") == "SELECT 2"


def test_saved_query_directory_deletes_one_file(tmp_path) -> None:
    from wherewolf.storage.saved_queries import SavedQueryDirectory

    root = tmp_path / "queries"
    library = SavedQueryDirectory(root)
    saved = library.save_query(name="daily", sql="SELECT 1")

    assert library.delete_query(saved.id)
    assert not (root / "daily.sql").exists()
    assert not library.delete_query(saved.id)


def test_saved_query_directory_writes_atomically(tmp_path, monkeypatch) -> None:
    from wherewolf.storage import saved_queries

    root = tmp_path / "queries"
    library = saved_queries.SavedQueryDirectory(root)
    library.save_query(name="daily", sql="SELECT 1")

    def fail(*_args: object) -> None:
        raise OSError("stop")

    monkeypatch.setattr(saved_queries.os, "replace", fail)

    with pytest.raises(OSError, match="stop"):
        library.save_query(name="second", sql="SELECT 2")

    assert (root / "daily.sql").read_text(encoding="utf-8") == "SELECT 1"
    assert [query.name for query in library.get_all()] == ["daily"]
