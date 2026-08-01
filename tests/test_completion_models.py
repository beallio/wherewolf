from dataclasses import FrozenInstanceError

import pytest

from wherewolf.domain.enums import CompletionKind
from wherewolf.domain.models import CompletionContext, CompletionItem


def test_completion_context_and_item_frozen_and_slotted() -> None:
    ctx = CompletionContext(sql="SELECT 1", cursor_offset=8, dialect="duckdb", catalog=())
    assert ctx.sql == "SELECT 1"
    assert ctx.cursor_offset == 8
    assert ctx.dialect == "duckdb"
    assert ctx.catalog == ()

    item = CompletionItem(
        label="orders",
        insert_text="orders",
        kind=CompletionKind.TABLE,
        detail="table",
        sort_key=(0, "orders"),
    )
    assert item.label == "orders"
    assert item.insert_text == "orders"
    assert item.kind == CompletionKind.TABLE
    assert item.detail == "table"
    assert item.sort_key == (0, "orders")

    with pytest.raises(FrozenInstanceError):
        setattr(ctx, "sql", "SELECT 2")  # noqa: B010

    with pytest.raises(FrozenInstanceError):
        setattr(item, "label", "customers")  # noqa: B010

    with pytest.raises(AttributeError):
        setattr(ctx, "custom_attr", 123)  # noqa: B010

    with pytest.raises(AttributeError):
        setattr(item, "custom_attr", 123)  # noqa: B010


def test_completion_items_with_different_kinds_are_distinct() -> None:
    item1 = CompletionItem(
        label="orders",
        insert_text="orders",
        kind=CompletionKind.TABLE,
        detail=None,
        sort_key=(0, "orders"),
    )
    item2 = CompletionItem(
        label="orders",
        insert_text="orders",
        kind=CompletionKind.CTE,
        detail=None,
        sort_key=(0, "orders"),
    )
    assert item1 != item2


def test_completion_item_empty_label_raises() -> None:
    with pytest.raises(ValueError, match="empty label"):
        CompletionItem(
            label="",
            insert_text="",
            kind=CompletionKind.KEYWORD,
            detail=None,
            sort_key=(0, ""),
        )
