from wherewolf.services.translation_view_model import translate_sql_view


def test_translation_view_model_same_dialect() -> None:
    sql = "SELECT 1;\nSELECT 2;"
    res = translate_sql_view(sql, "duckdb", "duckdb")
    assert res.translated_sql == sql
    assert len(res.diagnostics) == 0


def test_translation_view_model_multi_statement_no_statement_loss() -> None:
    # A real multi-statement query to assert N statements in -> N statements out
    sql = "SELECT a FROM table1;\nSELECT b FROM table2;\nSELECT c FROM table3;"
    res = translate_sql_view(sql, "duckdb", "spark")
    assert len(res.diagnostics) == 0
    # Must preserve all 3 statements
    lines = [line.strip() for line in res.translated_sql.split(";") if line.strip()]
    assert len(lines) == 3
    assert "table1" in lines[0]
    assert "table2" in lines[1]
    assert "table3" in lines[2]


def test_translation_view_model_untranslatable_produces_diagnostic() -> None:
    # Invalid SQL / dialect error produces SqlDiagnostic rather than raising
    sql = "SELECT * FROM dataset"
    res = translate_sql_view(sql, "invalid_dialect", "spark")
    assert len(res.diagnostics) == 1
    assert res.diagnostics[0].severity == "error"
    assert "unsupported" in res.diagnostics[0].message.lower()
