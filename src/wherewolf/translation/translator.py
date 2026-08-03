from typing import ClassVar

import sqlglot
from sqlglot.dialects import DIALECT_MODULE_NAMES

from wherewolf.domain.errors import TranslationError


class Translator:
    """Handles SQL dialect translation between DuckDB and SparkSQL."""

    VALID_DIALECTS: ClassVar[set[str]] = set(DIALECT_MODULE_NAMES)

    def translate(self, query: str, from_dialect: str, to_dialect: str) -> str:
        """Translates a SQL query from one dialect to another.

        Args:
            query: The SQL query string.
            from_dialect: The source dialect (e.g., 'duckdb').
            to_dialect: The target dialect (e.g., 'spark').

        Returns:
            The translated SQL query string.

        Raises:
            ValueError: If the dialect is not supported.
        """
        if from_dialect not in self.VALID_DIALECTS:
            raise ValueError(f"Unsupported source dialect: {from_dialect}")
        if to_dialect not in self.VALID_DIALECTS:
            raise ValueError(f"Unsupported target dialect: {to_dialect}")

        try:
            # sqlglot.transpile returns a list of translated queries
            translated = sqlglot.transpile(query, read=from_dialect, write=to_dialect, pretty=True)
            return translated[0] if translated else ""
        except Exception as e:
            # In a real app, we might want to warn about imperfect translation
            # for now, we'll re-raise or handle gracefully.
            raise ValueError(f"Translation failed: {e!s}") from e

    def translate_statements(
        self, query: str, from_dialect: str, to_dialect: str
    ) -> tuple[str, ...]:
        """Translate all statements in a query and preserve each statement."""
        if not query or not query.strip():
            return ()

        if from_dialect not in self.VALID_DIALECTS:
            raise ValueError(f"Unsupported source dialect: {from_dialect}")
        if to_dialect not in self.VALID_DIALECTS:
            raise ValueError(f"Unsupported target dialect: {to_dialect}")

        try:
            translated = sqlglot.transpile(
                query,
                read=from_dialect,
                write=to_dialect,
                pretty=True,
            )
            return tuple(translated)
        except Exception as e:
            raise TranslationError(f"Translation failed for query {query!r}: {e!s}") from e
