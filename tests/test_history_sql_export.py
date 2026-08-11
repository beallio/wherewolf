from wherewolf.services import serialise_history_records_to_sql


def _record(timestamp: str, query: object) -> dict[str, object]:
    return {"timestamp": timestamp, "query": query}


def test_serialise_history_records_to_sql_outputs_newest_first_with_exact_separation() -> None:
    records = [
        _record("2026-08-11T10:00:00+00:00", "SELECT 'oldest'"),
        _record("2026-08-11T12:00:00+00:00", "SELECT 'newest'"),
    ]

    assert serialise_history_records_to_sql(records) == (
        "-- 2026-08-11T12:00:00+00:00\n"
        "SELECT 'newest'\n"
        "\n"
        "-- 2026-08-11T10:00:00+00:00\n"
        "SELECT 'oldest'\n"
    )


def test_serialise_history_records_to_sql_returns_one_trailing_newline_for_single_record() -> None:
    assert serialise_history_records_to_sql([_record("2026-08-11T10:00:00+00:00", "SELECT 1")]) == (
        "-- 2026-08-11T10:00:00+00:00\nSELECT 1\n"
    )


def test_serialise_history_records_to_sql_returns_empty_text_without_records() -> None:
    assert serialise_history_records_to_sql([]) == ""


def test_serialise_history_records_to_sql_preserves_query_trailing_whitespace() -> None:
    assert serialise_history_records_to_sql(
        [_record("2026-08-11T10:00:00+00:00", "SELECT 1  ")]
    ) == ("-- 2026-08-11T10:00:00+00:00\nSELECT 1  \n")


def test_serialise_history_records_to_sql_avoids_extra_blank_line_for_queries_ending_in_newline() -> (
    None
):
    records = [
        _record("2026-08-11T12:00:00+00:00", "SELECT 'newest'\n"),
        _record("2026-08-11T10:00:00+00:00", "SELECT 'oldest'"),
    ]

    assert serialise_history_records_to_sql(records) == (
        "-- 2026-08-11T12:00:00+00:00\n"
        "SELECT 'newest'\n"
        "\n"
        "-- 2026-08-11T10:00:00+00:00\n"
        "SELECT 'oldest'\n"
    )


def test_serialise_history_records_to_sql_preserves_embedded_sql_comments() -> None:
    assert serialise_history_records_to_sql(
        [_record("2026-08-11T10:00:00+00:00", "SELECT 1 -- keep this comment")]
    ) == ("-- 2026-08-11T10:00:00+00:00\nSELECT 1 -- keep this comment\n")


def test_serialise_history_records_to_sql_skips_records_without_string_queries() -> None:
    records = [
        _record("2026-08-11T12:00:00+00:00", None),
        {"timestamp": "2026-08-11T11:00:00+00:00"},
        _record("2026-08-11T10:00:00+00:00", "SELECT retained"),
    ]

    assert serialise_history_records_to_sql(records) == (
        "-- 2026-08-11T10:00:00+00:00\nSELECT retained\n"
    )
