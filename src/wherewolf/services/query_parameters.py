"""Lexical helpers for named query parameters.

The scanner deliberately recognizes only the SQL surface needed for ``:name``
placeholders. It is not a SQL parser; callers must keep rewrites tied to the
spans it returns so comments, literals, and casts cannot drift out of sync.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParameterSpan:
    """The source span and name of one real named parameter."""

    name: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class DatasetTokenSpan:
    """The source span of one real ``{dataset}`` token."""

    start: int
    end: int


def parameter_spans(sql: str) -> tuple[ParameterSpan, ...]:
    """Return real ``:name`` placeholder spans, skipping SQL comments and literals."""
    spans: list[ParameterSpan] = []
    index = 0
    length = len(sql)
    while index < length:
        skipped_to = _skip_non_code(sql, index)
        if skipped_to is not None:
            index = skipped_to
        elif (
            sql[index] == ":"
            and (index == 0 or sql[index - 1] != ":")
            and index + 1 < length
            and _is_parameter_start(sql[index + 1])
        ):
            end = index + 2
            while end < length and _is_parameter_character(sql[end]):
                end += 1
            spans.append(ParameterSpan(sql[index + 1 : end], index, end))
            index = end
        else:
            index += 1
    return tuple(spans)


def dataset_token_spans(sql: str) -> tuple[DatasetTokenSpan, ...]:
    """Return real ``{dataset}`` token spans, skipping SQL comments and literals."""
    spans: list[DatasetTokenSpan] = []
    index = 0
    while index < len(sql):
        skipped_to = _skip_non_code(sql, index)
        if skipped_to is not None:
            index = skipped_to
        elif sql.startswith("{dataset}", index):
            end = index + len("{dataset}")
            spans.append(DatasetTokenSpan(index, end))
            index = end
        else:
            index += 1
    return tuple(spans)


def contains_dataset_token(sql: str) -> bool:
    """Return whether a query contains a bindable ``{dataset}`` token."""
    return bool(dataset_token_spans(sql))


def bind_dataset_tokens(sql: str, replacement: str) -> str:
    """Replace only real ``{dataset}`` tokens with an already quoted identifier."""
    parts: list[str] = []
    cursor = 0
    for span in dataset_token_spans(sql):
        parts.append(sql[cursor : span.start])
        parts.append(replacement)
        cursor = span.end
    parts.append(sql[cursor:])
    return "".join(parts)


def extract_parameters(sql: str) -> tuple[str, ...]:
    """Return distinct named placeholders in first-appearance order."""
    names: list[str] = []
    for span in parameter_spans(sql):
        if span.name not in names:
            names.append(span.name)
    return tuple(names)


def bind_parameters(sql: str, values: dict[str, str]) -> tuple[str, list[str]]:
    """Rewrite recognized placeholders to positional markers with ordered bound values."""
    parts: list[str] = []
    bound_values: list[str] = []
    cursor = 0
    for span in parameter_spans(sql):
        if span.name not in values:
            raise ValueError(f"Missing value for parameter :{span.name}")
        parts.append(sql[cursor : span.start])
        parts.append("?")
        bound_values.append(values[span.name])
        cursor = span.end
    parts.append(sql[cursor:])
    return "".join(parts), bound_values


def _skip_quoted(sql: str, index: int, quote: str) -> int:
    index += 1
    while index < len(sql):
        if sql[index] == quote:
            if index + 1 < len(sql) and sql[index + 1] == quote:
                index += 2
                continue
            return index + 1
        index += 1
    return index


def _skip_non_code(sql: str, index: int) -> int | None:
    """Return the index after a literal or comment beginning at ``index``."""
    character = sql[index]
    if character == "'":
        return _skip_quoted(sql, index, "'")
    if character == '"':
        return _skip_quoted(sql, index, '"')
    if sql.startswith("--", index):
        newline = sql.find("\n", index + 2)
        return len(sql) if newline == -1 else newline + 1
    if sql.startswith("/*", index):
        close = sql.find("*/", index + 2)
        return len(sql) if close == -1 else close + 2
    return None


def _is_parameter_start(character: str) -> bool:
    return character.isalpha() or character == "_"


def _is_parameter_character(character: str) -> bool:
    return character.isalnum() or character == "_"


__all__ = [
    "DatasetTokenSpan",
    "ParameterSpan",
    "bind_dataset_tokens",
    "bind_parameters",
    "contains_dataset_token",
    "dataset_token_spans",
    "extract_parameters",
    "parameter_spans",
]
