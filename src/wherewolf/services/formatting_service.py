"""SQL formatting service using SQLGlot."""

from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import errors

from wherewolf.domain import SqlDiagnostic
from wherewolf.services.statement_service import StatementService, StatementSpan


@dataclass(frozen=True)
class FormattingResult:
    """Result from formatting a SQL document."""

    formatted_sql: str | None
    diagnostics: tuple[SqlDiagnostic, ...]


class SqlFormattingService:
    """Format SQL documents using SQLGlot without changing dialect."""

    def __init__(self, statement_service: StatementService | None = None) -> None:
        self._statement_service = statement_service or StatementService()

    def format_sql(self, sql: str, dialect: str = "duckdb") -> FormattingResult:
        if not sql:
            return FormattingResult(formatted_sql=sql, diagnostics=())

        if not sql.strip():
            return FormattingResult(formatted_sql=sql, diagnostics=())

        line_ending = "\r\n" if "\r\n" in sql else "\n"

        try:
            spans = self._statement_service.split_statements(sql)
            if not spans:
                return FormattingResult(formatted_sql=sql, diagnostics=())

            formatted_chunks = [
                self._format_statement(sql, span, dialect=dialect) for span in spans
            ]
            formatted_sql = "\n".join(formatted_chunks)

            formatted_sql = formatted_sql.replace("\n", line_ending)

            return FormattingResult(
                formatted_sql=formatted_sql,
                diagnostics=(),
            )
        except errors.ParseError as exc:
            return FormattingResult(formatted_sql=sql, diagnostics=(self._build_diagnostic(exc),))

    def _format_statement(self, original_sql: str, span: StatementSpan, dialect: str) -> str:
        raw_segment = original_sql[span.start_offset : span.end_offset]
        has_trailing_semicolon = raw_segment.rstrip().endswith(";")
        if not raw_segment.strip():
            return ""

        formatted_candidates = sqlglot.transpile(
            raw_segment,
            read=dialect,
            write=dialect,
            pretty=True,
        )

        if not formatted_candidates:
            return span.text

        formatted = formatted_candidates[0]
        # Preserve semicolons only when present in the original segment.
        if has_trailing_semicolon and not formatted.rstrip().endswith(";"):
            formatted = f"{formatted.rstrip()};"
        if not has_trailing_semicolon:
            formatted = formatted.rstrip()
            formatted = formatted.removesuffix(";")

        return formatted

    @staticmethod
    def _build_diagnostic(exc: errors.ParseError) -> SqlDiagnostic:
        first = exc.errors[0] if exc.errors else None

        if first is None:
            return SqlDiagnostic(
                message=str(exc),
                severity="error",
                start_line=1,
                start_column=1,
                end_line=1,
                end_column=1,
            )

        return SqlDiagnostic(
            message=str(first.get("description", str(exc))),
            severity="error",
            start_line=int(first.get("line", 1)),
            start_column=int(first.get("col", 1)),
            end_line=int(first.get("line", 1)),
            end_column=int(first.get("col", 1)),
        )


__all__ = ["FormattingResult", "SqlFormattingService"]
