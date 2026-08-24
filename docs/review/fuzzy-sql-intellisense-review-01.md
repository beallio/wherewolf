# Review — fuzzy-sql-intellisense (round 01)

Branch: `feat/fuzzy-sql-intellisense`
Reviewed against: `docs/plans/2026-08-23_fuzzy-sql-intellisense.md`

## Verdict

Changes requested. The matcher, dynamic DuckDB/Spark catalogs, QScintilla user-list path,
engine synchronization, documentation, and reported mutation checks are substantially in
place. Review found two blocking statement/scope defects that the current tests do not cover.

## Gate status

- Round marker: valid at `b475dd4ca217ffb8b92a81235049d8538141c51a`.
- Primary feature worktree: clean before this review note was created.
- Focused independent check:
  `./run.sh uv run pytest -q --no-cov tests/test_completion_symbols.py tests/test_completion_service.py`
  passed 37 tests.
- The full quality gates and six mutation checks are recorded green in
  `docs/agent_conversations/2026-08-23_fuzzy-sql-intellisense.json`.
- Final approval gates were not rerun because the behavioral findings below require another
  implementation round first.

## Required changes

### 1. Isolate every completion source to the statement containing the cursor

`SqlCompletionService.complete()` passes the entire editor buffer to `_find_ctes()`,
`_find_tables_in_statement()`, and `_resolve_qualifier_to_table()`. Only the new alias collector
uses `StatementService`. This allows statement 1 to supply symbols and columns while completion
is requested in statement 2, contrary to the plan and the new durable spec.

Confirmed examples on `b475dd4`:

- `WITH old_cte AS (SELECT 1 AS x) SELECT * FROM old_cte; SELECT * FROM old` offers
  `old_cte` in the second statement.
- With `old_table(secret_old)` in the catalog,
  `SELECT x. FROM old_table x; SELECT x.` offers `secret_old` after the second statement's
  unresolved `x.`.
- With the same catalog, completion at `sec` in
  `SELECT * FROM old_table; SELECT sec FROM new_table` offers `secret_old` from statement 1.

Add failing regression tests first. Then isolate the current statement once, retain its relative
cursor offset, and ensure CTE discovery, table discovery, qualifier resolution, and alias
collection all consume that same statement slice. Preserve completion before `FROM` and the
existing incomplete-SQL fallback.

### 2. Associate SQLGlot SELECT nodes with lexical scopes by position/ancestry, not tuple index

`collect_symbols()` indexes a lexical, source-ordered `_scan_select_scopes()` tuple into
`parsed.find_all(exp.Select)`. SQLGlot visits an outer SELECT before a preceding CTE SELECT, while
the lexical scan sees the CTE SELECT first. The two orders therefore disagree.

Confirmed example on `b475dd4`:

```sql
WITH cte AS (SELECT source_id AS cte_alias FROM src s)
SELECT outer_id AS outer_alias FROM outer_table o ORDER BY outer_alias
```

At the outer `ORDER BY`, `collect_symbols()` returns `s` and `cte_alias` instead of `o` and
`outer_alias`; completion consequently loses the exact outer alias and leaks the inner scope.

Add Red coverage for both the outer-query cursor and a cursor inside the CTE, including service
completion assertions. Select the actual AST scope using identifier spans plus ancestry (or an
equally position-safe mapping) as required by the plan. Do not rely on traversal and lexical
tuples having identical order.

### 3. Keep the TDD/audit record accurate in the repair round

The Task 6 commit `cf579ea` already contains most Task 7 adapter/editor production changes,
while the session record's Task 6 Red result names only service failures and the first recorded
real Task 7 Red appears afterward. Do not rewrite the session log to imply the original ordering
was strict Red-Green. Add a concise process-deviation/remediation entry, create the new scope
regression tests before their fixes in this review round, record their exact Red failures and
Green results, and append the new gate/mutation evidence without deleting the existing history.

After the fixes, rerun the plan's focused completion checks, review-note integrity check, full
quality gates, and final negative control from a clean primary checkout. Add a disposable
mutation that reintroduces the CTE/outer-SELECT ordering bug or the cross-statement leak and
record the named failing nodes.

STATUS: CHANGES_REQUESTED
