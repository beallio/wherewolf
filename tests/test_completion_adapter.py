from unittest.mock import MagicMock

import pytest
from PyQt6.Qsci import QsciScintilla

from wherewolf.desktop.widgets.completion_adapter import CompletionAdapter
from wherewolf.domain.enums import CompletionKind, SourceFormat
from wherewolf.domain.models import CatalogEntry, ColumnSchema, CompletionContext, CompletionItem
from wherewolf.services.completion_service import SqlCompletionService


@pytest.fixture
def editor(qtbot):
    widget = QsciScintilla()
    qtbot.addWidget(widget)
    return widget


def test_completion_adapter_converts_items_and_shows_list(qtbot, editor):
    service = MagicMock(spec=SqlCompletionService)
    service.complete.return_value = (
        CompletionItem("orders", "orders", CompletionKind.TABLE, None, (0, "orders")),
        CompletionItem("customers", "customers", CompletionKind.TABLE, None, (0, "customers")),
    )

    adapter = CompletionAdapter(editor=editor, completion_service=service)
    catalog = ()
    ctx = CompletionContext(
        sql="SELECT * FROM ord", cursor_offset=17, dialect="duckdb", catalog=catalog
    )

    show_spy = MagicMock()
    editor.showUserList = show_spy

    adapter.request_completion(ctx)

    service.complete.assert_called_once_with(ctx)
    show_spy.assert_called_once()


def test_completion_adapter_empty_result_no_popup(qtbot, editor):
    service = MagicMock(spec=SqlCompletionService)
    service.complete.return_value = ()

    adapter = CompletionAdapter(editor=editor, completion_service=service)
    ctx = CompletionContext(sql="SELECT 'text'", cursor_offset=10, dialect="duckdb", catalog=())

    show_spy = MagicMock()
    editor.showUserList = show_spy

    adapter.request_completion(ctx)
    show_spy.assert_not_called()


def test_completion_adapter_replaces_only_typed_prefix(qtbot, editor):
    editor.setText("SELECT ord")
    editor.setCursorPosition(0, 10)

    service = SqlCompletionService()
    catalog = (
        CatalogEntry(
            id=MagicMock(),
            alias="orders",
            path=MagicMock(),
            source_format=SourceFormat.CSV,
            schema=(ColumnSchema("id", "INT"),),
        ),
    )

    adapter = CompletionAdapter(editor=editor, completion_service=service)
    ctx = CompletionContext(sql="SELECT ord", cursor_offset=10, dialect="duckdb", catalog=catalog)

    adapter.request_completion(ctx)

    # Simulate selecting "orders" from the list
    adapter.on_item_activated(1, "orders")

    assert editor.text() == "SELECT orders"
