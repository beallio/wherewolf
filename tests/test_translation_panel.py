from pytestqt.qtbot import QtBot

from wherewolf.desktop.widgets.translation_panel import TranslationPanel
from wherewolf.domain import EngineKind
from wherewolf.services import CatalogService, ExecutionRequestBuilder


def test_translation_panel_same_dialect(qtbot: QtBot) -> None:
    panel = TranslationPanel()
    qtbot.addWidget(panel)

    sql = "SELECT * FROM users LIMIT 10"
    panel.update_translation(sql=sql, source_dialect="duckdb", target_dialect="duckdb")

    assert panel.translated_text() == sql
    assert not panel.has_diagnostics()


def test_translation_panel_different_dialect(qtbot: QtBot) -> None:
    panel = TranslationPanel()
    qtbot.addWidget(panel)

    # DuckDB query translated to Spark
    sql = "SELECT * FROM users LIMIT 10"
    panel.update_translation(sql=sql, source_dialect="duckdb", target_dialect="spark")

    # The displayed statement is exactly the executable translation, not merely a label.
    translated = panel.translated_text()
    request = ExecutionRequestBuilder.build(
        sql=sql,
        source_dialect="duckdb",
        engine=EngineKind.SPARK,
        catalog_service=CatalogService(),
    )
    assert translated == request.executable_sql
    assert not panel.has_diagnostics()


def test_translation_panel_shows_diagnostics(qtbot: QtBot) -> None:
    panel = TranslationPanel()
    qtbot.addWidget(panel)

    sql = "SELECT * FROM users"
    panel.update_translation(sql=sql, source_dialect="invalid_dialect", target_dialect="spark")

    assert panel.has_diagnostics()
    assert "unsupported" in panel.diagnostics_text().lower()
