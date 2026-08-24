from wherewolf.services.completion_matching import (
    MAX_SUBSEQUENCE_SPAN,
    MatchQuality,
    match_identifier,
)


def test_match_identifier_classifies_documented_match_order() -> None:
    exact = match_identifier("date_trunc", "DATE_TRUNC")
    prefix = match_identifier("date", "DATE_TRUNC")
    token_initial = match_identifier("dt", "DATE_TRUNC")
    camel_token_initial = match_identifier("ci", "customerIdentifier")
    underscore_token_initial = match_identifier("ci", "customer_identifier")
    substring = match_identifier("sales", "monthly_sales")
    subsequence = match_identifier("drc", "DATE_TRUNC")

    assert exact is not None and exact.quality is MatchQuality.EXACT
    assert prefix is not None and prefix.quality is MatchQuality.PREFIX
    assert token_initial is not None and token_initial.quality is MatchQuality.TOKEN_INITIAL
    assert (
        camel_token_initial is not None
        and camel_token_initial.quality is MatchQuality.TOKEN_INITIAL
    )
    assert (
        underscore_token_initial is not None
        and underscore_token_initial.quality is MatchQuality.TOKEN_INITIAL
    )
    assert substring is not None and substring.quality is MatchQuality.SUBSTRING
    assert subsequence is not None and subsequence.quality is MatchQuality.SUBSEQUENCE

    assert exact < prefix < token_initial < substring < subsequence


def test_match_identifier_is_case_insensitive_and_rejects_weak_matches() -> None:
    assert match_identifier("TrUnC", "date_trunc") is not None
    assert match_identifier("dtr", "DATE_TRUNC") is not None
    assert match_identifier("dcz", "DATE_TRUNC") is None
    assert match_identifier("dx", "dabcdefghijklmnopqrstuvwx") is None


def test_match_identifier_bounds_ordered_subsequence_span() -> None:
    candidate = "d" + ("a" * MAX_SUBSEQUENCE_SPAN) + "t"

    assert match_identifier("dt", candidate) is None
    assert match_identifier("dt", "date_trunc") is not None


def test_match_identifier_scores_are_deterministic_and_support_empty_prefix() -> None:
    first = match_identifier("sa", "sales_amount")
    second = match_identifier("sa", "sales_amount")
    other = match_identifier("sa", "sales_archive")
    empty = match_identifier("", "DATE_TRUNC")

    assert first is not None
    assert first == second
    assert other is not None
    assert first.quality is other.quality is MatchQuality.PREFIX
    assert empty is not None and empty.quality is MatchQuality.EMPTY
