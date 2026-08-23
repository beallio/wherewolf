from wherewolf.services.execution_diagnostics import parse_duckdb_error_location


def test_parse_duckdb_error_location_maps_parser_caret_after_source_prefix() -> None:
    message = """Parser Error: syntax error at or near \"FROM\"

LINE 3:   FROM range(3)
          ^"""

    location = parse_duckdb_error_location(message)

    assert location is not None
    assert location.line == 3
    assert location.column == 3
    assert location.source_excerpt == "  FROM range(3)"


def test_parse_duckdb_error_location_maps_binder_caret_to_identifier_start() -> None:
    message = """Binder Error: Referenced column \"missing_column\" not found in FROM clause!
Candidate bindings: \"range\"

LINE 3: WHERE missing_column = 1
              ^"""

    location = parse_duckdb_error_location(message)

    assert location is not None
    assert location.line == 3
    assert location.column == 7
    assert location.source_excerpt == "WHERE missing_column = 1"


def test_parse_duckdb_error_location_maps_catalog_caret_on_later_line() -> None:
    message = """Catalog Error: Table with name foo does not exist!
Did you mean \"pg_collation\"?

LINE 4: JOIN foo ON range = foo.x
             ^"""

    location = parse_duckdb_error_location(message)

    assert location is not None
    assert location.line == 4
    assert location.column == 6
    assert location.source_excerpt == "JOIN foo ON range = foo.x"


def test_parse_duckdb_error_location_rejects_incomplete_or_unsafe_excerpts() -> None:
    messages = (
        "Parser Error: syntax error at end of input",
        "Binder Error: missing column",
        "LINE nope: SELECT 1\n            ^",
        "LINE 1: SELECT 1",
        "LINE 1: SELECT … FROM a_very_long_table\n               ^",
        "LINE 1: SELECT 1\n   ^",
    )

    assert [parse_duckdb_error_location(message) for message in messages] == [None] * len(messages)


def test_parse_duckdb_error_location_uses_final_coherent_triplet_only() -> None:
    message = """Binder Error: prose mentioning LINE 91: is not a location.
LINE 2: unmatched prose without a caret
Additional explanation.

LINE 5: ORDER BY missing_column
                 ^"""

    location = parse_duckdb_error_location(message)

    assert location is not None
    assert location.line == 5
    assert location.column == 10
    assert location.source_excerpt == "ORDER BY missing_column"
