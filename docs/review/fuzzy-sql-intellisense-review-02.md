# Review — fuzzy-sql-intellisense (round 02)

Branch: `feat/fuzzy-sql-intellisense`
Reviewed against: `docs/plans/2026-08-23_fuzzy-sql-intellisense.md`

## Verdict

Changes requested. Review round 1 fixed completion while the cursor is inside a second
statement, but the same isolation contract still fails when the cursor is in the empty fragment
after a statement terminator.

## Gate status

- Round marker: valid at `8370ec0aeb70ce31687f91ec15f05b46ede306d9`.
- Feature worktree: clean before this review note was created.
- Independent focused suite:
  `./run.sh uv run pytest -q --no-cov tests/test_completion_symbols.py tests/test_completion_service.py`
  passed 40 tests.
- The implementer recorded 292 focused checks, 869 default tests, review-note integrity, and the
  requested cross-statement mutation as green.
- A direct boundary assertion failed after those checks, so final approval remains blocked.

## Required changes

### Do not fall back to the whole document when the cursor has no current statement

`SqlCompletionService._current_statement()` returns the entire editor buffer when
`StatementService.find_statement()` cannot select a statement. That fallback is unsafe after a
semicolon: the cursor is in a new empty statement fragment, yet the preceding statement becomes
the completion context.

This command shape fails on `8370ec0`:

```python
sql = "WITH old_cte AS (SELECT * FROM old_table) SELECT * FROM old_table;\n  "
items = SqlCompletionService().complete(CompletionContext(sql, len(sql), "duckdb", catalog))
assert "old_cte" not in {item.label for item in items}
```

The actual list begins with `old_cte`, `old_table`, and DuckDB table functions because clause and
symbol discovery use statement 1. Add Red-first tests for a cursor immediately after a trailing
semicolon and after LF/CRLF whitespace following it. Prove CTEs, relation aliases, and columns
from the completed statement do not leak; general catalog/function/keyword completion may remain
available for the new empty fragment.

Change the no-selection path to return the cursor's empty/current fragment, not the full buffer.
Preserve the already-fixed behavior inside a real second statement, a single unterminated
statement at EOF, semicolons inside strings/comments, and ordinary empty/whitespace-only
documents. Record Red/Green results, add or extend the disposable mutation so this fallback is
load-bearing, rerun focused and full gates, update the session record, and mark the round complete
from a clean checkout.

STATUS: CHANGES_REQUESTED
