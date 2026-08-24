"""SQL statement location and extraction with quote/comment state tracking."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StatementSpan:
    """A SQL statement span in the source document."""

    text: str
    start_offset: int
    end_offset: int
    has_trailing_semicolon: bool


@dataclass(frozen=True)
class StatementSelection:
    """Result of locating a statement for a given cursor."""

    text: str | None
    start_offset: int
    end_offset: int
    reason: str | None = None


class StatementService:
    """Split SQL and locate statements with quote and comment awareness."""

    def split_statements(self, sql: str) -> tuple[StatementSpan, ...]:
        if not sql.strip():
            return ()

        statements: list[StatementSpan] = []

        in_single_quote = False
        in_double_quote = False
        in_line_comment = False
        in_block_comment = False
        escaped = False
        line_comment_boundary = False

        statement_start = 0
        statement_chars: list[str] = []
        statement_has_token = False

        cursor = 0
        while cursor < len(sql):
            char = sql[cursor]
            nxt = sql[cursor + 1] if cursor + 1 < len(sql) else None

            if in_line_comment:
                if char in ("\r", "\n"):
                    in_line_comment = False
                    line_comment_boundary = True
                cursor += 1
                continue

            if in_block_comment:
                statement_chars.append(char)
                if char == "*" and nxt == "/":
                    in_block_comment = False
                    statement_chars.append("/")
                    cursor += 2
                    continue

                statement_has_token = statement_has_token or char not in (" ", "\t")
                cursor += 1
                continue

            if in_single_quote:
                statement_chars.append(char)
                statement_has_token = True
                if escaped:
                    escaped = False
                    cursor += 1
                    continue

                if char == "\\":
                    escaped = True
                    cursor += 1
                    continue

                if char == "'":
                    if nxt == "'":
                        statement_chars.append("'")
                        cursor += 2
                        continue
                    in_single_quote = False
                cursor += 1
                continue

            if in_double_quote:
                statement_chars.append(char)
                statement_has_token = True
                if escaped:
                    escaped = False
                    cursor += 1
                    continue

                if char == "\\":
                    escaped = True
                    cursor += 1
                    continue

                if char == '"':
                    if nxt == '"':
                        statement_chars.append('"')
                        cursor += 2
                        continue
                    in_double_quote = False
                cursor += 1
                continue

            if char == "-" and nxt == "-":
                in_line_comment = True
                cursor += 2
                continue

            if char == "/" and nxt == "*":
                in_block_comment = True
                statement_chars.extend((char, "*"))
                statement_has_token = True
                cursor += 2
                continue

            if char == "'":
                in_single_quote = True
                statement_chars.append(char)
                statement_has_token = True
                cursor += 1
                continue

            if char == '"':
                in_double_quote = True
                statement_chars.append(char)
                statement_has_token = True
                cursor += 1
                continue

            if char == ";":
                statement = self._finalize_statement(
                    statement_start,
                    cursor + 1,
                    statement_chars,
                    statement_has_token,
                    has_trailing_semicolon=True,
                    from_line_comment_boundary=line_comment_boundary,
                )
                if statement is not None:
                    statements.append(statement)

                statement_start = cursor + 1
                while statement_start < len(sql) and sql[statement_start].isspace():
                    statement_start += 1
                statement_chars = []
                statement_has_token = False
                line_comment_boundary = False
                cursor += 1
                continue

            statement_chars.append(char)
            if not char.isspace():
                line_comment_boundary = False
            statement_has_token = statement_has_token or char not in (" ", "\t")
            cursor += 1

        trailing = self._finalize_statement(
            statement_start,
            len(sql),
            statement_chars,
            statement_has_token,
            has_trailing_semicolon=False,
            from_line_comment_boundary=False,
        )
        if trailing is not None:
            statements.append(trailing)

        return tuple(statements)

    def find_statement(self, sql: str, cursor_offset: int) -> StatementSelection:
        if cursor_offset < 0 or cursor_offset > len(sql):
            return StatementSelection(
                text=None,
                start_offset=-1,
                end_offset=-1,
                reason="cursor position is out of bounds",
            )

        statements = self.split_statements(sql)
        if not statements:
            return StatementSelection(
                text=None,
                start_offset=-1,
                end_offset=-1,
                reason="document is empty or whitespace-only",
            )

        for statement in statements:
            if statement.start_offset <= cursor_offset < statement.end_offset:
                return StatementSelection(
                    text=statement.text,
                    start_offset=statement.start_offset,
                    end_offset=statement.end_offset,
                )

        return StatementSelection(
            text=None,
            start_offset=-1,
            end_offset=-1,
            reason="no unambiguous statement for this cursor position",
        )

    @staticmethod
    def _finalize_statement(
        start: int,
        stop: int,
        statement_chars: list[str],
        has_token: bool,
        has_trailing_semicolon: bool,
        from_line_comment_boundary: bool = False,
    ) -> StatementSpan | None:
        if not has_token:
            return None

        statement_text = "".join(statement_chars).strip()
        if not statement_text:
            return None
        if has_trailing_semicolon and not from_line_comment_boundary:
            statement_text = f"{statement_text.rstrip()};"

        return StatementSpan(
            text=statement_text,
            start_offset=start,
            end_offset=stop,
            has_trailing_semicolon=has_trailing_semicolon,
        )


__all__ = ["StatementSelection", "StatementService", "StatementSpan"]
