# Review — headless-query-cli (round 01)

Branch: `feat/headless-query-cli`
Reviewed against: `docs/plans/2026-08-22_headless-query-cli.md`

## Verdict

The import boundary, dataset/output guards, adapter lifecycle, JSON Lines dispatch, and ordinary
query export are solid, and the full gates pass. Two user-visible command contracts are not yet
met: a valid statement with a trailing line comment fails when wrapped for export, and real DuckDB
errors can produce multiline stderr even though the CLI and README promise one concise line.

## Gate status

- `scripts/orchestration/run-quality-gates`: PASS (`724 passed, 7 deselected`; ruff check, ruff
  format check, `ty`, TDD enforcement, and review-note deletion check all passed).
- Branch/worktree before this review note: clean at `fe385b8` with a valid round-complete marker.
- Plan copy matches the preserved SHA-256
  `12bf46c6157bc77bebff00259c84ee60011b5d29f22bee1e37f440668e3c7acc`.

## Required changes

1. Build the executable SQL from the validated `StatementSpan.text`, removing only its final
   terminator, so a trailing line comment after that statement is excluded from the wrapped query.
   `_normalise_single_statement()` currently removes the semicolon from the original full string
   and retains the trailing comment. A real run of
   `wherewolf query 'SELECT 1 AS value; -- trailing comment' -o <new.csv>` exited 1 with
   `Parser Error: syntax error at end of input`. Add a real-adapter/CLI regression (not only a fake
   adapter assertion) covering this syntax through the COPY path and the separate XLSX count path,
   while retaining semicolons inside strings and comments within the statement.
2. Make expected validation/query/export failures produce exactly one concise
   `wherewolf query: ...` stderr line. A real `SELECT missing_column` currently emits the DuckDB
   headline plus a blank line, wrapped `COPY (...)` source excerpt, caret, and temporary output
   path. Normalize embedded newlines at the user-facing boundary and add a subprocess assertion for
   one newline total, empty stdout, exit 1, and no wrapped/temp SQL leakage. Also replace the broad
   `except Exception` in `_run_query()` with a specific user-facing service exception (or an
   equivalently explicit expected-exception boundary), as the plan requires unexpected programming
   errors to remain distinguishable rather than being silently converted to ordinary CLI failures.
3. Extend the durable acceptance evidence to include the real trailing-comment success cases and
   exact one-line multiline-DuckDB failure contract, then rerun the post-failure valid queries and
   full quality gates. Record exact commands, exit codes, and tallies in
   `docs/agent_conversations/2026-08-22_headless-query-cli.json`.

STATUS: CHANGES_REQUESTED
