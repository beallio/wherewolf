"""Dependency-free text case transforms for the desktop editor."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping

_ALPHANUMERIC_RUN = re.compile(r"[^\W_]+")
_LINE_TERMINATOR = re.compile(r"(\r\n|\r|\n)")


def split_words(text: str) -> tuple[str, ...]:
    """Split *text* into identifier-style words without splitting around digits."""

    words: list[str] = []
    for run in _ALPHANUMERIC_RUN.findall(text):
        start = 0
        for index in range(1, len(run)):
            previous = run[index - 1]
            character = run[index]
            following = run[index + 1] if index + 1 < len(run) else ""
            starts_camel_word = previous.islower() and character.isupper()
            starts_post_acronym_word = (
                previous.isupper() and character.isupper() and following.islower()
            )
            if starts_camel_word or starts_post_acronym_word:
                words.append(run[start:index])
                start = index
        words.append(run[start:])
    return tuple(words)


def to_lowercase(text: str) -> str:
    """Return *text* in lowercase without changing its separators."""

    return text.lower()


def to_uppercase(text: str) -> str:
    """Return *text* in uppercase without changing its separators."""

    return text.upper()


def _title_alphanumeric_run(match: re.Match[str]) -> str:
    run = match.group()
    return run[:1].upper() + run[1:].lower()


def to_title_case(text: str) -> str:
    """Title-case alphanumeric runs while preserving all separators."""

    return _ALPHANUMERIC_RUN.sub(_title_alphanumeric_run, text)


def to_camel_case(text: str) -> str:
    """Return identifier-style words joined in lower camel case."""

    words = split_words(text)
    if not words:
        return ""
    return words[0].lower() + "".join(word[:1].upper() + word[1:].lower() for word in words[1:])


def to_snake_case(text: str) -> str:
    """Return identifier-style words joined with underscores."""

    return "_".join(word.lower() for word in split_words(text))


def to_kebab_case(text: str) -> str:
    """Return identifier-style words joined with hyphens."""

    return "-".join(word.lower() for word in split_words(text))


def transform_lines(text: str, transform: Callable[[str], str]) -> str:
    """Apply *transform* to each non-blank line core, retaining whitespace and terminators."""

    transformed: list[str] = []
    for part in _LINE_TERMINATOR.split(text):
        if _LINE_TERMINATOR.fullmatch(part):
            transformed.append(part)
            continue

        core = part.strip()
        if not core:
            transformed.append(part)
            continue

        leading_length = len(part) - len(part.lstrip())
        trailing_length = len(part) - len(part.rstrip())
        trailing = part[-trailing_length:] if trailing_length else ""
        transformed.append(part[:leading_length] + transform(core) + trailing)
    return "".join(transformed)


TEXT_CASE_TRANSFORMS: Mapping[str, Callable[[str], str]] = {
    "lowercase": to_lowercase,
    "UPPERCASE": to_uppercase,
    "Title Case": to_title_case,
    "camelCase": to_camel_case,
    "snake_case": to_snake_case,
    "kebab-case": to_kebab_case,
}


__all__ = [
    "TEXT_CASE_TRANSFORMS",
    "split_words",
    "to_camel_case",
    "to_kebab_case",
    "to_lowercase",
    "to_snake_case",
    "to_title_case",
    "to_uppercase",
    "transform_lines",
]
