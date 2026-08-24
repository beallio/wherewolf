"""Deterministic, dependency-free matching for SQL completion labels."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

# A short query must not select nearly every identifier merely because its letters occur in
# order. The inclusive span between the first and final subsequence characters is limited to 16.
MAX_SUBSEQUENCE_SPAN = 16


class MatchQuality(IntEnum):
    """Match categories in the order completion candidates are ranked."""

    EXACT = 0
    PREFIX = 1
    TOKEN_INITIAL = 2
    SUBSTRING = 3
    SUBSEQUENCE = 4
    EMPTY = 5


@dataclass(frozen=True, order=True, slots=True)
class MatchScore:
    """Comparable score for an identifier match, lower values being stronger."""

    quality: MatchQuality


def _token_initials(label: str) -> str:
    initials: list[str] = []
    previous = ""
    for character in label:
        is_initial = (
            not previous or previous in "_- \t\r\n" or (previous.islower() and character.isupper())
        )
        if is_initial and character.isalnum():
            initials.append(character.casefold())
        previous = character
    return "".join(initials)


def _is_bounded_subsequence(query: str, candidate: str) -> bool:
    matched_positions: list[int] = []
    next_index = 0
    for character in query:
        position = candidate.find(character, next_index)
        if position < 0:
            return False
        matched_positions.append(position)
        next_index = position + 1

    return bool(matched_positions) and (
        matched_positions[-1] - matched_positions[0] + 1 <= MAX_SUBSEQUENCE_SPAN
    )


def match_identifier(query: str, candidate: str) -> MatchScore | None:
    """Return the documented fuzzy-match quality for *candidate*, or ``None``.

    Matching is case-insensitive. It deliberately does not attempt spelling correction or
    transpositions: after exact, prefix, token-initial, and substring checks, the final
    permissive case is a bounded ordered subsequence.
    """

    normalized_query = query.casefold()
    normalized_candidate = candidate.casefold()
    if not normalized_query:
        return MatchScore(MatchQuality.EMPTY)
    if normalized_query == normalized_candidate:
        return MatchScore(MatchQuality.EXACT)
    if normalized_candidate.startswith(normalized_query):
        return MatchScore(MatchQuality.PREFIX)
    if _token_initials(candidate).startswith(normalized_query):
        return MatchScore(MatchQuality.TOKEN_INITIAL)
    if normalized_query in normalized_candidate:
        return MatchScore(MatchQuality.SUBSTRING)
    if _is_bounded_subsequence(normalized_query, normalized_candidate):
        return MatchScore(MatchQuality.SUBSEQUENCE)
    return None


__all__ = ["MAX_SUBSEQUENCE_SPAN", "MatchQuality", "MatchScore", "match_identifier"]
