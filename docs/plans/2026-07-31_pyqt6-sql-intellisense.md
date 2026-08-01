# Plan: PyQt6 Desktop Migration - Schema-aware IntelliSense (Phase 7) (pyqt6-sql-intellisense)

## Context

Third slice of the PyQt6/QScintilla desktop migration. The full design is in
`docs/plans/2026-07-30-pyqt6-qscintilla-desktop-migration.md` (the "migration document").
**Read its Section 12.3 in full before starting** — it defines the completion contexts,
the ranking order, and the minimum cases that must work.

**This plan implements Phase 7 only: schema-aware SQL completion and call tips.**

Out of scope, each with its own later plan: query execution (Phase 8), the result grid
(Phase 9), schema/translation/messages panels (Phase 10), history and export
(Phases 11-12), Spark changes (Phase 13), Streamlit removal (Phase 14), release
(Phase 15).

This slice is deliberately split into small, single-deliverable tasks. Earlier slices
batched 13 tasks into one round and a round silently shipped 6 of 13. **Do not merge
tasks together. Do not skip ahead.** If a task cannot be completed as written, stop and say
so in the session log rather than working around it.

### What already exists — use it, do not rebuild it

Delivered by the previous slices, all merged to `dev`:

- **`src/wherewolf/domain/enums.py` already contains `CompletionKind`** with exactly
  `TABLE`, `CTE`, `COLUMN`, `FUNCTION`, `KEYWORD`, `SNIPPET`. Use it as-is.
- **`src/wherewolf/domain/models.py`** — frozen slotted `ColumnSchema(name, data_type,
  nullable)` and `CatalogEntry(id, alias, path, source_format, schema, schema_error)`.
  `CatalogEntry.schema` is `tuple[ColumnSchema, ...] | None`; `None` means *not loaded
  yet*, which is distinct from an empty tuple meaning *no columns*. Completion must treat
  those two cases differently.
- **`src/wherewolf/services/statement_service.py`** — `StatementService.split_statements()`
  and `.find_statement(sql, cursor_offset)`, returning `StatementSpan` /
  `StatementSelection`. It is already quote- and comment-aware and battle-tested. **Reuse
  it to isolate the statement under the cursor. Do not write a second statement parser.**
- **`src/wherewolf/services/catalog_service.py`** — `CatalogService.entries` (a property)
  gives `tuple[CatalogEntry, ...]`.
- **`src/wherewolf/desktop/widgets/sql_editor.py`** — `SqlEditor(QsciScintilla)` with
  `text_to_run()`, `format_selection_or_statement()`, `toggle_comment()`, `insert_text()`,
  find/replace, and a context menu. This is where the completion adapter attaches.
- **`src/wherewolf/translation/translator.py`** — has `translate_statements()`. Completion
  does **not** translate; do not route through it.

### Non-negotiable behavioral rules

From migration-document Section 12.3:

- **Never block the GUI thread on schema inspection.** Completion uses only already-cached
  `CatalogEntry.schema`. If schema is `None`, offer what you can and move on — do not
  trigger a load and wait.
- **The service must stay useful when SQL does not parse.** Users complete mid-typing, when
  SQLGlot will usually fail. A lexical/token fallback is mandatory, not optional.
- **No automatic popup inside a string literal or a comment.**
- **Insert appropriately quoted identifiers** when a name requires quoting.
- Automatic completion begins after a configurable threshold, default 2 characters;
  `Ctrl+Space` forces it even with an empty prefix.

### Hard constraint: Streamlit must keep working, unchanged

`src/wherewolf/app.py`, `engines.py`, `ui/`, `export/`, `storage/`, `constants.py` and
`.streamlit/` are **not modified by this plan**. `[project.scripts] wherewolf` keeps
pointing at `wherewolf.cli:main`.

### Repo mechanics that will fail your commits if ignored

- `.git/hooks/pre-commit` runs `ruff check .`, `ruff format .`, `ty check .` (whole repo,
  tests included), `pytest`, then `scripts/check_tdd.sh`.
- `scripts/check_tdd.sh` requires a **flat** `tests/test_<basename>.py` for every staged
  `src/**/*.py`. So `src/wherewolf/services/completion_service.py` requires
  `tests/test_completion_service.py`. **Flat names only**; do not create a nested tests
  tree and do not edit `check_tdd.sh`.
- ruff is on the **0.16 default rule set** (`I`, `BLE`, `UP`, `SIM`, `RUF`, `DTZ`, `B`,
  `PIE`, …). Any `except Exception` you add trips `BLE001`; annotate a deliberate boundary
  with `# noqa: BLE001` plus a one-line site-specific reason, matching
  `src/wherewolf/execution/`. Never a blanket ignore.
- All commands go through `./run.sh`.
- Qt tests run headless; `tests/conftest.py` already sets `QT_QPA_PLATFORM=offscreen`.

### Coverage and the known Qt crash

`[tool.coverage.run] timid = true` is set deliberately. It fixes a native crash where
coverage's C tracer corrupted frame state during PyQt6 event dispatch, which aborted the
suite on ~7-20% of runs. **Do not remove or change it.** It costs ~1.7x runtime (suite is
~24s, not ~14s); that is expected and accepted.

`scripts/check_flake.sh N` runs the suite N times under coverage and fails on any native
crash. Because this plan adds Qt widget and event-driven code — exactly the area that
provoked the original crash — the Verification section requires running it.

### Baseline

`dev` at `a913e04`: **179 passed, 1 skipped**, `ruff check` / `ruff format --check` /
`ty check src/` all clean. Any failure in your baseline run is a real problem; investigate
before writing code.

**Slug used throughout this plan:** `pyqt6-sql-intellisense`

---

## Orchestration Contract

**Slug:** `pyqt6-sql-intellisense`

**Plan file:**

```text
docs/plans/2026-07-31_pyqt6-sql-intellisense.md
```

**Implementation branch:**

```text
feat/pyqt6-sql-intellisense
```

**Round-complete marker:**

```text
/tmp/wherewolf/pyqt6-sql-intellisense_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/pyqt6-sql-intellisense_finalized
```

**Review notes:**

```text
docs/review/pyqt6-sql-intellisense-review-*.md
```

Each review note ends with exactly one status trailer:

```text
STATUS: CHANGES_REQUESTED
```

or:

```text
STATUS: APPROVED
```

---

## Required Agent Protocol

1. Use the **implementer** skill.
2. Work from the repository root.
3. Branch from `dev`.
4. Commit this plan as the first commit on the implementation branch.
5. Follow TDD where behavior changes are testable.
6. Run quality gates before marking any round complete.
7. Do not write your own review.
8. Do not create files under `docs/review/`.
9. Do not delete files under `docs/review/`.
10. Review notes are durable audit records and must be committed.
11. Resolving a review note means:
    - implement the requested changes;
    - run quality gates;
    - commit the code/docs changes;
    - commit the review note itself if it is not already committed;
    - recreate the round-complete marker.
12. After finalization, stop polling and exit cleanly.

---

## Scope discipline

- Implement only the units the plan lists. Do not modify files outside the plan's scope.
- Do not change runtime behavior beyond what the plan specifies. A `refactor` or
  `cleanup` commit must preserve observable behavior.
- Never edit a test's expected value to make a behavior change pass. If a test
  legitimately must change, that change must be required by the plan or a review
  note, and you must record the rationale in the session log.
- If you spot an unrelated improvement, do not make it here — note it in the
  session log for a separate plan.

---

## Setup

Start from `dev`:

```bash
git checkout dev
# ORCH_LOCAL_ONLY: local trial branch, skipping origin pull
git checkout -b feat/pyqt6-sql-intellisense
```

Commit this plan first:

```bash
git add docs/plans/2026-07-31_pyqt6-sql-intellisense.md
git commit -m "docs(plan): add pyqt6-sql-intellisense implementation plan"
```

---

## Implementation Tasks

**Twelve small tasks, one deliverable each, one commit each.** Write the failing test
first, watch it fail, then implement. Run `./run.sh uv run pytest` after every task.

Commit the session log in Task 1 and append to it as you go — do not leave it to the end.

Tasks 2-8 are pure logic with **no Qt imports at all**. Qt appears only from Task 9.

---

### Task 1 — Session log and baseline

Emit the `AGENT_PROTOCOL_HANDSHAKE` from `AGENTS.md` Section 1. Create **and commit**
`docs/agent_conversations/2026-07-31_pyqt6-sql-intellisense.md` with the Section 14
headings.

```bash
./run.sh uv sync --all-extras --dev
./run.sh uv run pytest -q 2>&1 | tail -3
```

Expected `179 passed, 1 skipped`. Record it and `git rev-parse HEAD`.

Commit: `docs: record sql intellisense baseline`.

---

### Task 2 — Completion domain records

**Red.** `tests/test_completion_models.py`: `CompletionContext` and `CompletionItem` are
frozen and slotted; `CompletionItem.sort_key` is a `tuple[int, str]`; two items with
different kinds but equal labels are distinct; a `CompletionItem` cannot be constructed
with an empty `label`.

**Green.** Add to `src/wherewolf/domain/models.py` exactly the shapes from
migration-document Section 8.5:

```python
CompletionContext(sql: str, cursor_offset: int, dialect: str, catalog: tuple[CatalogEntry, ...])
CompletionItem(label: str, insert_text: str, kind: CompletionKind, detail: str | None, sort_key: tuple[int, str])
```

`tests/test_models.py` already exists and covers that module, so `check_tdd.sh` is
satisfied; the new file is for readability.

Commit: `feat(domain): add SQL completion records`.

---

### Task 3 — Lexical cursor-context detector

The foundation everything else rests on. **Pure lexer — no SQLGlot.** It must work on
SQL that does not parse.

**Red.** `tests/test_completion_context.py`. Given SQL and a cursor offset, classify the
context. Cover at minimum:

- immediately after `FROM ` → `TABLE_REF`
- after `JOIN ` → `TABLE_REF`
- after `alias.` → `QUALIFIED_COLUMN`, and report the alias text
- inside `SELECT`, `WHERE`, `GROUP BY`, `HAVING`, `ORDER BY` → `COLUMN_REF`
- **inside a single-quoted string → `SUPPRESSED`**
- **inside a `--` line comment → `SUPPRESSED`**
- **inside a `/* */` block comment → `SUPPRESSED`**
- an unterminated string still suppresses to end of document
- empty document, and cursor at offset 0
- the partial word under the cursor is reported as the prefix, empty when on whitespace
- a cursor immediately after `.` gives an empty prefix with a non-empty alias
- **badly broken SQL still classifies** — e.g. `SELECT * FRO` , `SELECT a, FROM`,
  `SELECT * FROM orders WHERE x = ` all return a usable context rather than raising

**Green.** `src/wherewolf/services/completion_context.py`. Use `StatementService` to
narrow to the statement under the cursor, then scan tokens backwards. Return a frozen
result carrying the context kind, the prefix, and the qualifying alias when present.

Commit: `feat(services): add lexical SQL cursor-context detection`.

---

### Task 4 — Dialect keyword and function metadata

**Red.** `tests/test_sql_metadata.py`: DuckDB and Spark each return a non-empty keyword
set and a non-empty function set; a few known members are present for each
(`SELECT`/`QUALIFY` for DuckDB, `SELECT`/`LATERAL VIEW` for Spark); functions carry a
signature string usable as a call tip; lookup is case-insensitive; an unknown dialect
raises rather than silently returning empty.

**Green.** `src/wherewolf/services/sql_metadata.py`. Source keywords/functions from SQLGlot
where it exposes them, and supplement with an explicit curated list. Do not hand-roll
hundreds of entries; a solid, tested core set is sufficient for this phase.

Commit: `feat(services): add dialect keyword and function metadata`.

---

### Task 5 — Completion service: catalog aliases

First real completion behavior. Migration-document Section 12.3 minimum case 1.

**Red.** `tests/test_completion_service.py`:

```sql
SELECT *
FROM <cursor>
```

suggests every catalog alias, kind `TABLE`. Also: a prefix filters case-insensitively
(`FROM ord` → `orders`); an empty catalog returns no table suggestions without raising;
suggestions in a `SUPPRESSED` context are empty.

**Green.** `src/wherewolf/services/completion_service.py` with
`SqlCompletionService.complete(context: CompletionContext) -> tuple[CompletionItem, ...]`.
Deterministic, no Qt, no I/O.

Commit: `feat(services): suggest catalog aliases in FROM and JOIN`.

---

### Task 6 — Completion service: `alias.` column resolution

Migration-document Section 12.3 minimum cases 2 and 3 — the headline feature.

**Red.** Extend `tests/test_completion_service.py`:

```sql
SELECT o.<cursor>
FROM orders AS o
```

returns **only** `orders` columns. Then:

```sql
SELECT *
FROM orders o
JOIN customers c
  ON o.customer_id = c.<cursor>
```

prioritises `customers` columns. Also cover: alias without `AS`; the bare table name used
as its own qualifier (`orders.<cursor>`); an **unknown** alias returns no columns rather
than every column; an entry whose `schema is None` (not yet loaded) yields no columns and
**does not raise or block**; an entry with an empty-tuple schema is treated as *no
columns*, distinct from not-loaded.

**Green.** Resolve aliases from the statement text. Try SQLGlot for accurate scope
resolution; on `ParseError`, fall back to the lexical scan from Task 3. Both paths must be
tested — parametrise so each assertion runs against parseable and deliberately broken SQL.

Commit: `feat(services): resolve alias-qualified column completions`.

---

### Task 7 — CTE names and columns

**Red.** `tests/test_completion_service.py` additions:

```sql
WITH recent AS (SELECT * FROM orders)
SELECT * FROM <cursor>
```

suggests `recent` with kind `CTE` alongside catalog aliases. A qualified `recent.<cursor>`
offers the CTE's columns when derivable from the inner `SELECT`; when not derivable, it
returns nothing rather than guessing. Multiple CTEs all appear. A CTE shadowing a catalog
alias appears once, as the CTE.

**Green.** Extend the service. SQLGlot AST where possible, lexical fallback otherwise.

Commit: `feat(services): complete CTE names and derivable CTE columns`.

---

### Task 8 — Ranking and identifier quoting

**Red.** `tests/test_completion_service.py` additions. Assert the exact ordering from
migration-document Section 12.3: exact case-insensitive prefix match, then resolved
`alias.` column, then in-scope table/CTE, then unambiguous in-scope column, then function,
then keyword, then fuzzy. Build a fixture where several kinds match one prefix and assert
the resulting `label` order explicitly — not merely that each item is present.

Also: an identifier needing quotes (a space, a reserved word, mixed case where the dialect
folds) has `insert_text` correctly quoted while `label` stays human-readable; function
items insert `name(`; ordering is stable for equal-ranked items (sort is deterministic
across runs).

**Green.** Implement ranking via `CompletionItem.sort_key`. Quote using the active
dialect's rules, not string concatenation.

Commit: `feat(services): rank completions and quote identifiers`.

---

### Task 9 — Call tips

**Red.** `tests/test_completion_service.py`: `call_tip(context)` returns the signature when
the cursor sits inside a known function's parentheses; `None` outside any call, for an
unknown function, and inside a string or comment; nested calls report the innermost.

**Green.** Add `call_tip()` to the service, sourcing signatures from Task 4's metadata.

Commit: `feat(services): add SQL function call tips`.

---

### Task 10 — QScintilla completion adapter

First Qt task. Keep presentation here and logic in the service.

**Red.** `tests/test_completion_adapter.py` with `qtbot`. **Register every widget with
`qtbot.addWidget`** — unregistered top-level widgets caused real problems in earlier
slices:

- the adapter converts `tuple[CompletionItem, ...]` into a QScintilla user list;
- selecting an item replaces **only the typed prefix**, not the whole word or line;
- each `CompletionKind` maps to a distinct visual marker (image/type id);
- an empty result shows no popup;
- the adapter calls the service exactly once per request (spy the service);
- no popup is shown for a `SUPPRESSED` context.

**Green.** `src/wherewolf/desktop/widgets/completion_adapter.py`. It owns QScintilla APIs
(`showUserList`, `SCN_USERLISTSELECTION`, registered images) and holds **no completion
logic**.

Commit: `feat(editor): add QScintilla completion presentation adapter`.

---

### Task 11 — Wire into the editor: threshold, `Ctrl+Space`, settings

**Red.** `tests/test_sql_editor.py` additions:

- typing reaching the configured threshold (default 2) requests completion;
- below the threshold does not;
- **`Ctrl+Space` forces completion with an empty prefix**;
- automatic completion can be disabled via settings, and `Ctrl+Space` still works when it
  is off;
- the threshold round-trips through `SettingsService` with the existing versioned-key and
  scoped-fallback pattern;
- **the GUI thread is never blocked**: with a `CatalogEntry` whose `schema is None`, a
  completion request still returns promptly and shows no columns;
- a "Show Completion" `QAction` exists, is enabled, and is the **same object** in the Query
  menu and the editor context menu (assert with `is`) — matching the Run/Cancel/Format
  convention.

**Green.** Wire `SqlEditor` → adapter → service. Debounce automatic requests. Add the
action to `build_actions()` and both menus. Persist threshold and enable/disable.

Commit: `feat(editor): wire schema-aware completion into the SQL editor`.

---

### Task 12 — README and close out the session log

Update `README.md`: the desktop shell now offers schema-aware SQL completion and call tips;
state plainly that **query execution is still not implemented**. Bump `cacheBuster` from
`13` to `14` on README image/badge URLs per `AGENTS.md` Section 13.

Finish the session log: files per task, tests added, baseline vs final tallies, every
deviation with its reason, and everything not verified.

Commit: `docs: document schema-aware SQL completion`.

---

## Quality Gates

Run before marking any round complete:

```bash
scripts/orchestration/run-quality-gates
scripts/orchestration/check-review-notes-not-deleted
git status --short
```

The round is not complete unless:

1. all requested implementation work is done;
2. all relevant tests pass;
3. build/typecheck gates pass;
4. review notes have not been deleted;
5. the working tree is clean;
6. all code/docs changes are committed.

---

## Verification

Written to the standard in
`~/.claude/skills/orchestration-plan-author/references/verification-standards.md`. Every
step can fail and says what failure looks like. Run in order — V5 breaks things
deliberately and V6 is the negative control that must run **after** the tree is restored.

Report output, not conclusions.

### V1 — Suite and gates

```bash
set -o pipefail
cd "$(git rev-parse --show-toplevel)"

output=$(./run.sh uv run pytest -q 2>&1)
printf '%s\n' "$output" | tail -5

failed=$(printf '%s\n' "$output" | awk '/^FAILED /{print $2}')
if [ -n "$failed" ]; then
  echo "FAIL: baseline is green, so any failure is a regression:"; printf '%s\n' "$failed"; exit 1
fi
passed=$(printf '%s\n' "$output" | grep -oE '[0-9]+ passed' | tail -1 | cut -d' ' -f1)
if [ -z "$passed" ] || [ "$passed" -le 179 ]; then
  echo "FAIL: passed count is '${passed:-<none>}', expected greater than 179"; exit 1
fi
echo "OK: 0 failures; $passed passed (baseline 179)"
```

Then `scripts/orchestration/run-quality-gates`, which **must exit 0**.

**Failure looks like:** any failing test, a passed count at or below 179, or a non-zero
gate exit.

### V2 — The minimum completion cases from the migration document actually work

These three are the reason this phase exists. Assert them end-to-end through the service,
not by reading the code:

```bash
./run.sh uv run pytest -q --no-cov tests/test_completion_service.py -v 2>&1 | tail -25
```

Every one of these must be present and passing:

1. `SELECT * FROM <cursor>` → catalog aliases.
2. `SELECT o.<cursor> FROM orders AS o` → **only** `orders` columns.
3. `SELECT * FROM orders o JOIN customers c ON o.customer_id = c.<cursor>` → prioritises
   `customers` columns.

**Failure looks like:** any of the three missing, skipped, or asserting only that the
result is non-empty. "Returns something" is not the requirement; case 2 must return
*only* that table's columns.

### V3 — Broken SQL still completes, and strings/comments stay silent

```bash
./run.sh uv run pytest -q --no-cov tests/test_completion_context.py tests/test_completion_service.py 2>&1 | tail -3
```

Then confirm by hand that the unparseable-SQL fallback is genuinely exercised rather than
assumed:

```bash
./run.sh uv run python -c "
from wherewolf.services.completion_service import SqlCompletionService
from wherewolf.services.completion_context import detect_context
for sql in ['SELECT * FRO', 'SELECT a, FROM', 'SELECT * FROM orders WHERE x = ', \"SELECT 'abc\"]:
    print(repr(sql), '->', detect_context(sql, len(sql)))
"
```

Adapt the import names to what you actually built. **Failure looks like:** an exception on
any of these, or the unterminated-string case not reporting a suppressed context.

### V4 — No Qt in the service layer

Completion logic must remain UI-neutral and independently testable.

```bash
grep -rn "PyQt6\|QtCore\|QtWidgets\|Qsci" src/wherewolf/services/ src/wherewolf/domain/ \
  && echo "FAIL: Qt leaked into services/domain" || echo "OK: services and domain are Qt-free"
```

**Failure looks like:** any hit. The adapter in `src/wherewolf/desktop/widgets/` is the
only place QScintilla APIs may appear.

### V5 — Mutation checks: prove the new tests bite

**Commit first** — every check ends in `git checkout --`, which against an uncommitted tree
destroys the round. Revert fully between each and confirm `git status --short` is clean.

When a mutation needs an added import, place it **after** any
`from __future__ import annotations`, or you get a `SyntaxError` and a collection error —
an inconclusive result, not a passing one.

1. **Context detector ignores strings.** Make the detector treat quotes as ordinary
   characters. → the string/comment suppression tests in `tests/test_completion_context.py`
   must FAIL.
2. **`alias.` returns all columns.** Make qualified completion ignore the alias and return
   every catalog column. → the "only `orders` columns" test must FAIL.
3. **Ranking collapses.** Make `sort_key` a constant. → the explicit ordering test in
   `tests/test_completion_service.py` must FAIL.
4. **Quoting dropped.** Make `insert_text` always equal `label`. → the identifier-quoting
   test must FAIL.
5. **Threshold ignored.** Make the editor request completion on every keystroke. → the
   below-threshold test in `tests/test_sql_editor.py` must FAIL.
6. **Prefix replacement broken.** Make the adapter insert without removing the typed
   prefix. → the prefix-replacement test in `tests/test_completion_adapter.py` must FAIL.

Record the exact failing node ID for each. Then:

```bash
git checkout -- src/ tests/
git status --short
```

**Must print nothing.**

### V6 — No native crash regression, then negative control

This slice adds Qt widget and event-driven code — the exact area that caused the coverage
crash fixed in `a913e04`. Confirm it has not returned:

```bash
scripts/check_flake.sh 25
```

**Pass condition: `PASSED: 0 native crashes in 25 runs`.** **Failure looks like:** any
crash count, or the script reporting an ordinary test failure (exit 2), which is a real
regression rather than flake.

Do not shorten the 25 runs. The original bug ran at ~7-20%; a handful of runs cannot
distinguish "fixed" from "lucky", which is exactly how it evaded detection for four review
rounds.

Then the negative control:

```bash
set -o pipefail
git status --short
./run.sh uv run ruff check .
./run.sh uv run ruff format --check .
./run.sh uv run ty check src/
scripts/orchestration/check-review-notes-not-deleted
```

`git status --short` must print nothing. V5 has just shown that removing any of six
load-bearing behaviors turns the suite red, so a clean sweep here is not something an empty
implementation could produce.

### Deferred and explicitly NOT verified

State all of this in the final report and the session log. An unstated gap reads as a
covered one.

- **No completion popup was ever seen by a human.** Every Qt test runs under
  `QT_QPA_PLATFORM=offscreen`; the adapter is asserted through QScintilla's API, not
  visually. That the popup renders, positions correctly, and is readable is **manual,
  deferred** verification.
- **No real typing.** Debounce and threshold are tested through synthesised events, not
  actual keyboard input timing.
- **macOS and Windows unverified**, including whether `Ctrl+Space` conflicts with the
  platform input-method switcher on macOS — a known collision worth flagging in the log.
- **The 100 ms completion latency target in migration-document Section 12.3 was not
  measured.** It is an engineering target, not a CI gate; say so rather than implying it
  was met.
- **Completion quality is bounded by cached schema.** Entries with `schema is None`
  contribute no columns; this is by design (never block the GUI thread) and is a real
  functional limit worth recording.
- **No query executes.** Run stays disabled; execution is Phase 8. Do not describe the
  desktop app as functional.
- **CI unproven until first push**, as with every phase so far.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished pyqt6-sql-intellisense
```

This writes:

```text
/tmp/wherewolf/pyqt6-sql-intellisense_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer pyqt6-sql-intellisense`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/pyqt6-sql-intellisense-review-*.md
```

When a review note exists or a new review note appears:

1. Read the full review note.
2. If the note ends with:

   ```text
   STATUS: CHANGES_REQUESTED
   ```

   then resume work.

3. Clear the round-complete marker:

   ```bash
   scripts/orchestration/clear-finished pyqt6-sql-intellisense
   ```

4. Address every requested change.
5. Run quality gates:

   ```bash
   scripts/orchestration/run-quality-gates
   scripts/orchestration/check-review-notes-not-deleted
   ```

6. Commit code/docs fixes.
7. Commit the review-note file itself if it is not already committed:

   ```bash
   git add docs/review/pyqt6-sql-intellisense-review-*.md
   git commit -m "docs(review): record pyqt6-sql-intellisense review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished pyqt6-sql-intellisense
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer pyqt6-sql-intellisense` after the next review note is created.

---

## Approval Handling

If the latest review note ends with:

```text
STATUS: APPROVED
```

then:

1. Confirm every previous review item has been addressed.
2. Confirm all review notes are committed:

   ```bash
   scripts/orchestration/check-review-notes-committed pyqt6-sql-intellisense
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize pyqt6-sql-intellisense
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/pyqt6-sql-intellisense_finalized
   ```

6. Stop polling and exit cleanly.

---

## Review Rules

Do not write your own review.

Do not create files under:

```text
docs/review/
```

Do not delete files under:

```text
docs/review/
```

Only the orchestrator writes review notes. Your job is to read them, resolve them, commit them as audit records, and continue the loop.

---

## Finalization Rules

Only finalize after a review note with:

```text
STATUS: APPROVED
```

Finalization is performed with:

```bash
scripts/orchestration/finalize pyqt6-sql-intellisense
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/pyqt6-sql-intellisense_finished
/tmp/wherewolf/pyqt6-sql-intellisense_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
