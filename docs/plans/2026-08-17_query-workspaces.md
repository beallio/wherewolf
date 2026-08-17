# Plan: Editor tabs and saved query library (query-workspaces)

## Context

This plan covers items 7 and 12 from `feature-ideation-ui-quality-of-life.md`. It is the
**third** of three sequenced plans and depends on `workspace-persistence` having merged
into `dev` — Unit A below generalises the single-buffer draft persistence that plan
introduces, and Unit B stores queries alongside the catalog store it creates. Branch
from `dev` only after that merge.

### Defect A — there is only one editor

`self.editor` is a single `SqlEditor` instance throughout
`src/wherewolf/desktop/main_window.py` (constructed once, referenced at `:508`, `:761`,
`:857`, `:1009`, `:1013`, `:1047`, `:1051`, `:1084` among others). Every real analysis
session involves holding more than one query at a time: the working query, the one that
built the reference table, and the scratch `SELECT DISTINCT` being re-run to check a
value. Today the only way to keep a second query is to paste it outside the application,
which is the clearest "I have to leave the app for this" signal in the product.

The pattern already exists in the codebase — the results side is a `QTabWidget`
(`main_window.py:882`) — so this is generalising an established idiom, not introducing a
new one.

### Defect B — history remembers what you ran, not what you rely on

Query history answers "what did I run". It does not answer "what do I run every Monday".
An analyst checking the same five data-quality rules against each week's export
currently re-finds them in history and hand-edits the alias each time. The 0.8.0 round
added "save selected history records as SQL"
(`src/wherewolf/services/history_sql_export.py`), which is the halfway point: queries can
leave, but they cannot be named, parameterised, or re-bound to a different dataset.

### Intended outcome

- Multiple SQL editor tabs, restored on launch, each with its own results.
- A saved-query library holding named queries with `:param` placeholders and an optional
  dataset binding, runnable from a dock.

### Design decisions already made

Settled with the user; do not revisit.

- **Tabs come before the library.** Unit A must be complete and committed before Unit B
  starts. Building the library against a single-buffer editor and then retrofitting tabs
  would be rework.
- **Three distinct surfaces for SQL, all retained.** Auto-restored drafts (from
  `workspace-persistence`), Open/Save `.sql` files (likewise), and this named library.
  They serve different jobs; do not collapse them or remove either of the first two.
- **The library storage mirrors `HistoryManager`.** `~/.wherewolf/saved_queries.json`,
  atomic `tempfile.mkstemp` + `os.replace`, versioned entries with a migration path. Do
  not use `QSettings` and do not add a database.
- **Parameter substitution must not be string interpolation into SQL.** See B3; this is
  a correctness and injection concern, and the repo already has
  `tests/test_duckdb_sql_injection.py` guarding this class of bug.

**Slug used throughout this plan:** `query-workspaces`

---

## Orchestration Contract

**Slug:** `query-workspaces`

**Plan file:**

```text
docs/plans/2026-08-17_query-workspaces.md
```

**Implementation branch:**

```text
feat/query-workspaces
```

**Round-complete marker:**

```text
/tmp/wherewolf/query-workspaces_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/query-workspaces_finalized
```

**Review notes:**

```text
docs/review/query-workspaces-review-*.md
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
git pull --ff-only origin dev
git checkout -b feat/query-workspaces
```

Commit this plan first:

```bash
git add docs/plans/2026-08-17_query-workspaces.md
git commit -m "docs(plan): add query-workspaces implementation plan"
```

---

## Implementation Tasks

Each task is **atomic**: one coherent behavior change, its own failing test first, its
own commit, independently verifiable. Do not batch two tasks into one commit. Run
`scripts/orchestration/run-quality-gates` before each commit.

Unit A must be fully committed before Unit B begins.

### Unit A — Multiple editor tabs

This unit touches many call sites. Do it in the order below; A1 exists specifically so
that A2 becomes a mechanical change rather than a risky one.

**A1. Introduce an editor-accessor seam.** *(one commit, no behavior change)*

Before adding any tabs, add a `current_editor` property on `MainWindow` returning
`self.editor`, and replace every direct `self.editor` reference with
`self.current_editor`. Keep `self.editor` as the single instance for now.

This commit must be a pure refactor: observable behavior identical, full suite green,
no test changes. It is what makes A2 a small diff.

**On the TDD rule.** `AGENTS.md` §9 says implementation code without a failing test
created earlier in the same session is invalid. That rule targets *behavior* changes;
this task deliberately changes none, so there is no behavior to write a failing test for,
and writing one would mean asserting that `current_editor is self.editor` — a tautology.
The enforced gate, `scripts/check_tdd.sh`, requires only that a matching
`tests/test_<module>.py` exists for each changed `src/**.py` file; `tests/test_main_window.py`
already does, so this commit passes it. Record this exemption and its reasoning in the
session log so a reviewer does not read it as a TDD violation.

Verify by running the full suite before and after and recording that the tallies are
identical.

**A2. Replace the single editor with a tab widget.** *(one commit)*

Add `self.editor_tabs: QTabWidget` with `setTabsClosable(True)` and `setMovable(True)`.

`setTabsClosable(True)` only draws the close button — it does not close anything. You
must connect `editor_tabs.tabCloseRequested` to a handler that removes the tab. Wiring
the flag without the signal produces a close button that silently does nothing, which
will pass a naive "the button exists" test.
`current_editor` now returns the widget at the current tab index, or `None` when no tabs
remain. Construct one tab at startup so behavior matches today's single-editor case.

Every consumer of `current_editor` must handle `None` — closing the last tab must not
raise. Prefer keeping at least one tab open by re-creating an empty tab when the last is
closed; state whichever you choose in the session log.

Add actions `new_tab` (`Ctrl+T`) and `close_tab` (`Ctrl+W`) to `DesktopActions`
(`src/wherewolf/desktop/actions.py`) and wire them into the File menu.

`workspace-persistence` B2 tracks the open file as a single window-global
`self._current_sql_path`, which is wrong once tabs exist — Save would write tab 2's buffer
to tab 1's file. Move that state onto the tab: each editor tab owns its own path and
dirty flag, and Save/Save As/window title read the *current* tab's. Migrating that field
is part of this task, not a follow-up.

Tab labels come from the saved filename when there is one (from
`workspace-persistence` B2), otherwise the first non-empty line of the SQL truncated to
~30 characters, otherwise `Untitled`.

Test first: a new window has exactly one tab; `Ctrl+T` adds one and focuses it; typing
in one tab does not alter another's buffer; closing a tab removes it; closing the last
tab does not raise.

**A3. Per-tab results.** *(one commit)*

Running a query must populate the results view for the tab that ran it, and switching
tabs must show that tab's last result rather than the other tab's. Store the last
`QueryResult` per tab and re-render on tab change. The class is `QueryResult`, defined at
`src/wherewolf/domain/models.py:86` (there is a second, distinct `QueryResult` at
`src/wherewolf/execution/models.py:7` — confirm which one the results view actually
consumes before storing it). There is no `ExecutionResult` type in this repo.

A query still running when the user switches tabs must not write its result into the
now-current tab. The `filename-and-value-counts-ux` round already established this
pattern for value-counts workers (`_current_worker` guard); apply the same idea, keyed
on the originating tab.

Test first: run a result into tab 1, switch to tab 2, and assert the results view is
empty or shows tab 2's own result — not tab 1's. Then deliver a result that originated
in tab 1 while tab 2 is current, and assert tab 2's view is unchanged. That second
assertion is the one that catches the cross-tab leak.

**A4. Restore tabs on launch.** *(one commit)*

Generalise the single-buffer draft persistence added in `workspace-persistence` B1 from
one string to a list of `{text, path}` records plus the active tab index. Keep the old
single-string key readable as a one-tab migration so an upgrading user does not lose
their draft.

Test first: persist three tabs, rebuild the window, assert all three come back with the
right text and the right active index. Separately, seed the **old** single-string
settings key and assert it restores as exactly one tab — that is the migration
assertion.

### Unit B — Saved-query library

**B1. `SavedQueryStore` — pure storage, no Qt.** *(one commit)*

Create `src/wherewolf/storage/saved_queries.py` modelled on
`src/wherewolf/storage/history.py`:

- `DEFAULT_PATH = Path.home() / ".wherewolf" / "saved_queries.json"`.
- Records: `id`, `name`, `description`, `sql`, `created_at`, `updated_at`.
- `save_query`, `update_query`, `delete_query`, `get_all`, `get_by_id`.
- Atomic writes via `tempfile.mkstemp` + `os.replace`; versioned wrapper
  `{"version": 1, "queries": [...]}`; malformed records skipped, not fatal.

Test in a new `tests/test_saved_query_store.py` against `tmp_path`: round trip; duplicate
names rejected or disambiguated (state which in the session log); corrupt file loads
empty rather than raising; an interrupted write leaves the previous file intact.

**B2. Extract parameters from SQL.** *(one commit, pure function)*

Add `extract_parameters(sql: str) -> tuple[str, ...]` to a new
`src/wherewolf/services/query_parameters.py`, returning the distinct `:name` placeholders
in order of first appearance.

It must **not** match: `::` casts (`value::int` is DuckDB/Postgres cast syntax, not a
parameter), `:name` inside single- or double-quoted string literals, or `:name` inside
`--` line comments and `/* */` block comments.

Test first, and make the tests adversarial: `SELECT a::int FROM t` yields no parameters;
`SELECT ':notaparam'` yields none; `-- :nope` yields none; `SELECT * FROM t WHERE a = :x AND b = :y AND c = :x`
yields exactly `("x", "y")`. Getting `::` wrong is the most likely bug here and it is
silent — the query still runs, just with a mangled cast.

**B3. Bind parameters safely.** *(one commit)*

Add `bind_parameters(sql: str, values: dict[str, str]) -> tuple[str, list]` producing SQL
with placeholders replaced by the engine's positional marker and a matching ordered
value list.

It must skip exactly what B2 skips — `::` casts, quoted literals, and comments. Do not
re-scan the string with a second, looser rule: have B2's scanner return the character
**spans** of the real placeholders and have `bind_parameters` rewrite only those spans.
Two independent scanners will drift apart, and the failure is silent — a `:name` inside a
string literal would be rewritten into a positional marker, changing what the query
means. Refactor B2 to expose spans as part of this task if it does not already.

**Do not interpolate values into the SQL string.**

Be aware of what does and does not exist. `duckdb_engine.py:31,34` uses `params=[...]`,
but only for *internal* file-reading statements (`read_json_auto`, `read_xlsx`). The
user-query path, `execute()` at `duckdb_engine.py:62`, does **not** currently accept
parameters, and `tests/test_duckdb_sql_injection.py` covers the file-path case, not
user-supplied query parameters. So there is no ready-made bound-parameter path for user
queries to reuse — this task has to add one.

Extend the engine's `execute()` signature to accept an optional ordered parameter list
and pass it through to DuckDB, keeping the parameter default empty so every existing
caller is unaffected. Do the same for the Spark adapter or explicitly raise there and
record the limitation in the session log — do not silently fall back to string
substitution on one engine while binding on the other.

If extending `execute()` turns out to be infeasible within this plan's scope, **stop and
say so in the session log**. Shipping string interpolation instead is not an acceptable
fallback.

Test first: a value containing `'; DROP TABLE t; --` is transported as data and does not
alter the statement's structure. That test must fail against a naive string-replacement
implementation.

**B4. Saved-queries dock.** *(one commit)*

Add `src/wherewolf/desktop/widgets/saved_queries_dock.py` — a list of saved queries with
a filter box, and context actions Run, Open in New Tab, Rename, Delete. Add a
`Save Current Query…` action to `DesktopActions` that captures the current editor buffer
with a prompted name.

Running a query with parameters prompts for values first, one field per extracted
parameter, and runs via the binding from B3. Register the dock in the window's dock
layout and include it in `Reset Layout`.

Test first: saving the current buffer makes it appear in the dock; Run on a
parameterless query executes it; Run on a parameterised query prompts and passes the
entered values through `bind_parameters`; the filter narrows the list.

**B5. Bind a saved query to a dataset.** *(one commit)*

Support an optional `{dataset}` placeholder resolved to a catalog alias chosen at run
time, so the same rule can run against this week's file. The alias must be quoted with
`src/wherewolf/services/identifier_quoting.py:quote_identifier` — an alias is an
identifier, not a value, so it cannot go through B3's value binding.

Test first: a query containing `{dataset}` prompts for an alias, substitutes the quoted
identifier, and an alias requiring quoting (spaces, or a reserved word) is quoted
correctly.

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

Every step must be able to fail. Before adding a step of your own, answer: *what state of
the world makes this print the failure output?* If the answer is "none" or "only if the
tool is broken", it is decoration — delete it. Report actual output, not conclusions.

```bash
export QT_QPA_PLATFORM=offscreen
set -o pipefail
```

**`set -o pipefail` is mandatory for every step in this section.** Without it,
`pytest ... | tail` reports `tail`'s exit status and a failing suite is indistinguishable
from a passing one. Set it again in any fresh shell. Where a step below shows
`echo "exit=$?"`, that exit code is the authoritative result, not the summary line.

As in `workspace-persistence`: **no test may write to the real `~/.wherewolf/`.** Inject
a `tmp_path` store or `QSettings` everywhere, and reuse that plan's V2 snapshot check
here — this plan adds a third store file, `saved_queries.json`, to the same directory.

### V1 — Baseline

```bash
./run.sh uv run pytest -q; echo "pytest exit=$?"
```

### V2 — Prove A1 changed nothing

A1 is a pure refactor, so its verification is an equality check, and it is meaningful
precisely because it can fail.

**Do not use `git stash` / `git stash pop` for this.** If a stash already exists, `pop`
restores the wrong one; if the working tree is dirty, the stash silently swallows
unrelated work; and if the suite crashes between the two commands the changes are left
stashed with no obvious trace. Compare committed revisions instead, which is
non-destructive and needs no clean tree:

```bash
base=$(git rev-parse HEAD~1)   # the commit before A1
head=$(git rev-parse HEAD)     # A1 itself

git diff --name-only "$base" "$head" | tee /tmp/wherewolf/a1-files.txt
if grep -q '^tests/' /tmp/wherewolf/a1-files.txt; then
  echo "FAIL: A1 touched a test file; it was not a pure refactor -- split it"
  exit 1
fi

git worktree add /tmp/wherewolf/a1-base "$base"
(cd /tmp/wherewolf/a1-base && ./run.sh uv run pytest -q); echo "base exit=$?"
./run.sh uv run pytest -q; echo "head exit=$?"
git worktree remove /tmp/wherewolf/a1-base
```

The two tallies must be identical and both exits must be 0. The `grep` on the changed
file list is the assertion that catches a "refactor" that quietly edited a test to keep
itself green.

### V3 — Per-unit suites

```bash
./run.sh uv run pytest tests/test_main_window.py -q               # Unit A
./run.sh uv run pytest tests/test_saved_query_store.py \
                      tests/test_query_parameters.py -q           # Unit B
```

### V4 — Prove parameter extraction is not naive

B2 is the task most likely to look correct and be wrong, because the failure is silent —
a mangled `::` cast still parses and still runs.

```bash
./run.sh uv run pytest tests/test_query_parameters.py -q -v; echo "exit=$?"
```

Confirm by inspection that the suite contains the `::` cast case, the quoted-literal
case, and the comment case. A suite that only tests `WHERE a = :x` does not cover this.

### V5 — Prove parameter binding resists injection

```bash
./run.sh uv run pytest tests/ -q -k "injection or bind" -v; echo "exit=$?"
```

There must be a test passing `'; DROP TABLE t; --` as a **value** and asserting the
statement structure is unchanged. Then confirm it is load-bearing: temporarily
reimplement `bind_parameters` as naive `str.replace` and record the test going red.
If it stays green, the test is not testing binding.

### V6 — Prove results do not leak across tabs

```bash
./run.sh uv run pytest tests/test_main_window.py -q -k "tab" -v; echo "exit=$?"
```

There must be a test that delivers a result originating in tab 1 while tab 2 is current
and asserts tab 2's view is unchanged. A test that only checks "switching tabs shows a
different result" does not cover the in-flight case.

### V7 — Mutation gates (negative controls)

After V1–V6. Apply, run the suite, record it going **red**, revert, confirm green.

| # | Mutation | Suite that must go red |
|---|---|---|
| 1 | Make `current_editor` always return the tab-0 editor | `tests/test_main_window.py` |
| 2 | Drop the originating-tab guard so any result renders into the current tab | `tests/test_main_window.py` |
| 3 | Drop the old single-string settings key migration in A4 | `tests/test_main_window.py` |
| 4 | In `query_parameters.py`, match `:name` with a bare regex ignoring `::` and quotes | `tests/test_query_parameters.py` |
| 5 | Reimplement `bind_parameters` as naive `str.replace` | injection suite |
| 6 | In `saved_queries.py`, let `load` raise on malformed JSON | `tests/test_saved_query_store.py` |
| 7 | In B5, substitute the dataset alias without `quote_identifier` | saved-query dock suite |
| 8 | Set `setTabsClosable(True)` but disconnect `tabCloseRequested` | `tests/test_main_window.py` |
| 9 | Keep the file path window-global instead of per-tab | `tests/test_main_window.py` |
| 10 | Have `bind_parameters` re-scan with its own looser rule instead of B2's spans | `tests/test_query_parameters.py` |

Mutations 8, 9 and 10 all produce features that look implemented and fail silently: a
close button that does nothing, a Save that writes the wrong tab's buffer to a file, and
a placeholder rewritten inside a string literal.

### V8 — Full gates

```bash
scripts/orchestration/run-quality-gates
git status --short
```

Record the ruff, ty and pytest tallies as printed.

### Deferred and unverified

- **No performance measurement with many tabs.** Ten or twenty open tabs each holding a
  result frame will hold significant memory; nothing here measures it or bounds it.
- **Parameter typing is string-only.** Every prompted value is bound as text; there is no
  date, numeric, or list parameter support, and no test covers type coercion.
- **`extract_parameters` is not a SQL parser.** It is a lexer-level scan. Exotic dialect
  syntax (dollar-quoted strings, nested block comments) is not covered, and `sqlglot` is
  already a dependency if that turns out to matter — flag it rather than expanding scope
  here.
- **Dialog interactions are monkeypatched** for the parameter prompt and the save-name
  prompt, so broken dialog wiring would not be caught.
- **No Windows verification**, consistent with the two prior plans.
- **Tab restoration is not tested against a crash**, only against a clean close. A hard
  kill may leave the settings mid-write.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished query-workspaces
```

This writes:

```text
/tmp/wherewolf/query-workspaces_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer query-workspaces`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/query-workspaces-review-*.md
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
   scripts/orchestration/clear-finished query-workspaces
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
   git add docs/review/query-workspaces-review-*.md
   git commit -m "docs(review): record query-workspaces review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished query-workspaces
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer query-workspaces` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed query-workspaces
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize query-workspaces
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/query-workspaces_finalized
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
scripts/orchestration/finalize query-workspaces
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/query-workspaces_finished
/tmp/wherewolf/query-workspaces_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
