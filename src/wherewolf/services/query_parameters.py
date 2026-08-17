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


def parameter_spans(sql: str) -> tuple[ParameterSpan, ...]:
    """Return real ``:name`` placeholder spans, skipping SQL comments and literals."""
    spans: list[ParameterSpan] = []
    index = 0
    length = len(sql)
    while index < length:
        character = sql[index]
        if character == "'":
            index = _skip_quoted(sql, index, "'")
        elif character == '"':
            index = _skip_quoted(sql, index, '"')
        elif sql.startswith("--", index):
            newline = sql.find("\n", index + 2)
            index = length if newline == -1 else newline + 1
        elif sql.startswith("/*", index):
            close = sql.find("*/", index + 2)
            index = length if close == -1 else close + 2
        elif (
            character == ":"
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


def _is_parameter_start(character: str) -> bool:
    return character.isalpha() or character == "_"


def _is_parameter_character(character: str) -> bool:
    return character.isalnum() or character == "_"


__all__ = ["ParameterSpan", "bind_parameters", "extract_parameters", "parameter_spans"]
