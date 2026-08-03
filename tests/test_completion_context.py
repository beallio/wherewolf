from wherewolf.services.completion_context import CursorContextKind, detect_context


def test_detect_context_table_ref_from_and_join() -> None:
    ctx = detect_context("SELECT * FROM ", 14)
    assert ctx.kind == CursorContextKind.TABLE_REF
    assert ctx.prefix == ""
    assert ctx.qualifier is None

    ctx_partial = detect_context("SELECT * FROM ord", 17)
    assert ctx_partial.kind == CursorContextKind.TABLE_REF
    assert ctx_partial.prefix == "ord"
    assert ctx_partial.qualifier is None

    ctx_join = detect_context("SELECT * FROM orders JOIN cust", 30)
    assert ctx_join.kind == CursorContextKind.TABLE_REF
    assert ctx_join.prefix == "cust"
    assert ctx_join.qualifier is None


def test_detect_context_qualified_column() -> None:
    ctx = detect_context("SELECT o. FROM orders o", 9)
    assert ctx.kind == CursorContextKind.QUALIFIED_COLUMN
    assert ctx.prefix == ""
    assert ctx.qualifier == "o"

    ctx_partial = detect_context("SELECT o.id_num FROM orders o", 11)
    assert ctx_partial.kind == CursorContextKind.QUALIFIED_COLUMN
    assert ctx_partial.prefix == "id"
    assert ctx_partial.qualifier == "o"


def test_detect_context_column_ref_clauses() -> None:
    for sql_clause in [
        "SELECT ",
        "SELECT a, ",
        "SELECT * FROM orders WHERE ",
        "SELECT * FROM orders GROUP BY ",
        "SELECT * FROM orders HAVING ",
        "SELECT * FROM orders ORDER BY ",
    ]:
        ctx = detect_context(sql_clause, len(sql_clause))
        assert ctx.kind == CursorContextKind.COLUMN_REF, f"Failed on {sql_clause}"


def test_detect_context_suppressed_strings_and_comments() -> None:
    # Single quoted string
    ctx_str = detect_context("SELECT 'hello world'", 12)
    assert ctx_str.kind == CursorContextKind.SUPPRESSED

    # Unterminated string
    ctx_unterm = detect_context("SELECT 'abc", 11)
    assert ctx_unterm.kind == CursorContextKind.SUPPRESSED

    # Line comment
    ctx_line_cmt = detect_context("SELECT * FROM orders -- checking columns", 30)
    assert ctx_line_cmt.kind == CursorContextKind.SUPPRESSED

    # Block comment
    ctx_block_cmt = detect_context("SELECT /* comment inside */ * FROM orders", 15)
    assert ctx_block_cmt.kind == CursorContextKind.SUPPRESSED


def test_detect_context_empty_and_zero_offset() -> None:
    ctx_empty = detect_context("", 0)
    assert ctx_empty.kind in (CursorContextKind.COLUMN_REF, CursorContextKind.TABLE_REF)
    assert ctx_empty.prefix == ""

    ctx_zero = detect_context("SELECT * FROM orders", 0)
    assert ctx_zero.prefix == ""


def test_detect_context_badly_broken_sql() -> None:
    for sql in [
        "SELECT * FRO",
        "SELECT a, FROM",
        "SELECT * FROM orders WHERE x = ",
    ]:
        ctx = detect_context(sql, len(sql))
        assert ctx.kind != CursorContextKind.SUPPRESSED
