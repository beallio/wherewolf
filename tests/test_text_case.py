import pytest

from wherewolf.services.text_case import TEXT_CASE_TRANSFORMS, split_words, transform_lines


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("customer_order_id", ("customer", "order", "id")),
        ("fooBar", ("foo", "Bar")),
        ("HTTPResponseCode", ("HTTP", "Response", "Code")),
        ("total sales 2026", ("total", "sales", "2026")),
        ("order2id", ("order2id",)),
        ("kebab-case-name", ("kebab", "case", "name")),
        ("SCREAMING_SNAKE", ("SCREAMING", "SNAKE")),
        ("", ()),
        ("___", ()),
    ],
)
def test_split_words_segments_every_identifier_style(text: str, expected: tuple[str, ...]) -> None:
    assert split_words(text) == expected


@pytest.mark.parametrize(
    ("text", "label", "expected"),
    [
        ("customer_order_id", "lowercase", "customer_order_id"),
        ("customer_order_id", "UPPERCASE", "CUSTOMER_ORDER_ID"),
        ("customer_order_id", "Title Case", "Customer_Order_Id"),
        ("customer_order_id", "camelCase", "customerOrderId"),
        ("customer_order_id", "snake_case", "customer_order_id"),
        ("customer_order_id", "kebab-case", "customer-order-id"),
        ("customerOrderId", "lowercase", "customerorderid"),
        ("customerOrderId", "UPPERCASE", "CUSTOMERORDERID"),
        ("customerOrderId", "Title Case", "Customerorderid"),
        ("customerOrderId", "camelCase", "customerOrderId"),
        ("customerOrderId", "snake_case", "customer_order_id"),
        ("customerOrderId", "kebab-case", "customer-order-id"),
        ("HTTPResponseCode", "lowercase", "httpresponsecode"),
        ("HTTPResponseCode", "UPPERCASE", "HTTPRESPONSECODE"),
        ("HTTPResponseCode", "Title Case", "Httpresponsecode"),
        ("HTTPResponseCode", "camelCase", "httpResponseCode"),
        ("HTTPResponseCode", "snake_case", "http_response_code"),
        ("HTTPResponseCode", "kebab-case", "http-response-code"),
        ("total sales 2026", "lowercase", "total sales 2026"),
        ("total sales 2026", "UPPERCASE", "TOTAL SALES 2026"),
        ("total sales 2026", "Title Case", "Total Sales 2026"),
        ("total sales 2026", "camelCase", "totalSales2026"),
        ("total sales 2026", "snake_case", "total_sales_2026"),
        ("total sales 2026", "kebab-case", "total-sales-2026"),
        ("SCREAMING_SNAKE", "lowercase", "screaming_snake"),
        ("SCREAMING_SNAKE", "UPPERCASE", "SCREAMING_SNAKE"),
        ("SCREAMING_SNAKE", "Title Case", "Screaming_Snake"),
        ("SCREAMING_SNAKE", "camelCase", "screamingSnake"),
        ("SCREAMING_SNAKE", "snake_case", "screaming_snake"),
        ("SCREAMING_SNAKE", "kebab-case", "screaming-snake"),
        ("kebab-case-name", "lowercase", "kebab-case-name"),
        ("kebab-case-name", "UPPERCASE", "KEBAB-CASE-NAME"),
        ("kebab-case-name", "Title Case", "Kebab-Case-Name"),
        ("kebab-case-name", "camelCase", "kebabCaseName"),
        ("kebab-case-name", "snake_case", "kebab_case_name"),
        ("kebab-case-name", "kebab-case", "kebab-case-name"),
        ("order2id", "lowercase", "order2id"),
        ("order2id", "UPPERCASE", "ORDER2ID"),
        ("order2id", "Title Case", "Order2id"),
        ("order2id", "camelCase", "order2id"),
        ("order2id", "snake_case", "order2id"),
        ("order2id", "kebab-case", "order2id"),
    ],
)
def test_each_transform_matches_the_specified_behaviour(
    text: str, label: str, expected: str
) -> None:
    assert TEXT_CASE_TRANSFORMS[label](text) == expected


def test_transform_lines_preserves_line_terminators() -> None:
    text = "a_b\r\nc_d\re_f\ng_h"

    assert transform_lines(text, TEXT_CASE_TRANSFORMS["camelCase"]) == "aB\r\ncD\reF\ngH"


def test_transform_lines_preserves_indentation_and_trailing_whitespace() -> None:
    assert (
        transform_lines("    customer_id  ", TEXT_CASE_TRANSFORMS["camelCase"])
        == "    customerId  "
    )


def test_transform_lines_leaves_blank_lines_untouched() -> None:
    text = "alpha_one\n\n   \n beta_two "

    assert transform_lines(text, TEXT_CASE_TRANSFORMS["camelCase"]) == "alphaOne\n\n   \n betaTwo "


def test_text_case_transforms_registry_is_ordered_and_complete() -> None:
    assert list(TEXT_CASE_TRANSFORMS) == [
        "lowercase",
        "UPPERCASE",
        "Title Case",
        "camelCase",
        "snake_case",
        "kebab-case",
    ]
