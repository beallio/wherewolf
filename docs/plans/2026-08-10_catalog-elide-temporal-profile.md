# Plan: Fix catalog File column elision and temporal profiling failure (catalog-elide-temporal-profile)

## Context

Two independent user-reported defects. Both root causes were reproduced before
this plan was written; the reproductions are restated below so you can rebuild
them rather than trust them.

### Defect A — the catalog File column never shows the filename

`CatalogModel.data` (`src/wherewolf/desktop/models/catalog_model.py:72`) returns
the full absolute path as `DisplayRole`, and `CatalogDock`
(`src/wherewolf/desktop/widgets/catalog_dock.py:46-58`) never sets
`textElideMode`, so `QTableView`'s default `ElideRight` applies. Elide-right keeps
the shared directory *prefix* and discards the basename — the only part that
distinguishes one row from another.

Measured with `QFontMetrics.elidedText` at the default application font against
`C:\Users\dbeall\OneDrive - Contoso\Documents\Analytics\2026\exports\customers.parquet`:

| Section width | Rendered text |
|---|---|
| 100 px | `C:\Users\dbea…` |
| 200 px | `C:\Users\dbeall\OneDrive - Cont…` |
| 400 px | `C:\Users\dbeall\OneDrive - Contoso\Documents\Analytics\2026\exp…` |
| 522 px | first width at which the filename appears |

The whole catalog dock in the user's screenshot (`fix/Screenshot_20260802_132729.png`)
is roughly 450 px wide, so no reachable column width reveals the filename. That is
why the user reports that resizing the column changes nothing.

Two contributing factors, both real:

- `CatalogDock` sets no `setSectionResizeMode` and no `setStretchLastSection`,
  unlike `history_dock.py:54-56` and `schema_panel.py:86-87`. Every column sits at
  the 100 px default forever and nothing — dock resize, content length, layout
  reset — ever adapts it.
- The `ToolTipRole` at `catalog_model.py:79` is currently the only way to see the
  full path.

The rendering path itself is **not** broken: programmatically setting the File
section to 380 px does reveal more text, and section sizes survive the
`beginResetModel`/`endResetModel` cycle in `CatalogModel._on_catalog_changed`. Do
not go looking for a header bug; there isn't one.

### Defect B — profiling dies on temporal columns

`_as_float` in `src/wherewolf/execution/registry.py:583`:

```python
def _as_float(value: object) -> float | None:
    return float(str(value)) if value is not None else None
```

DuckDB's `SUMMARIZE` returns `avg`, `std`, `q25`, `q50`, `q75` as **VARCHAR**, and
for temporal columns those values are temporal literals, not numbers.
`float("2024-01-01 06:56:39.5")` raises `ValueError`, which the handler at
`registry.py:264` converts into a `ProfileResult` carrying
`error_type="ValueError"` and empty `profiles`. One bad column destroys the entire
profile.

End-to-end reproduction against `_DuckDBAdapter.profile_dataset`, with a CSV whose
timestamps are written as text:

```text
error_type: ValueError
error_message: could not convert string to float: '2024-01-01 06:56:39.5'
profiles: ()
```

Two corrections to the original bug report, both verified:

- **Dataset size is irrelevant.** A 100-row CSV fails identically to a
  50,000-row one. Do not write a large fixture to reproduce this.
- **"Stored as strings" is not the trigger; the sniffed type is.** A column that
  stays `VARCHAR` is safe — DuckDB returns `NULL` for its quantiles. The user's
  CSV fails precisely *because* `read_csv_auto` promotes the text timestamps to
  `TIMESTAMP`.

Measured failing types: `TIMESTAMP`, `TIMESTAMP WITH TIME ZONE`, `DATE`, `TIME`.
Measured safe types: `VARCHAR`, `BOOLEAN`, `HUGEINT`, `DOUBLE`, `BIGINT`.

### Chosen fixes

Both shapes were decided by the user before this plan was written. Do not
substitute a different approach.

- **A:** `ElideMiddle` on the catalog view plus the resize modes the other docks
  already use. The full path stays the display text and the tooltip.
- **B:** Widen `ColumnProfile.avg/std/q25/q50/q75` to `str | None` and pass
  `SUMMARIZE`'s text through verbatim, exactly as `min`/`max` already do, so
  temporal columns keep their real mean and quartiles. A tolerant `_as_float` that
  returns `None` was explicitly rejected: it would blank those statistics forever
  and the user could not distinguish "not applicable" from "not computed".

### Blast radius

`ColumnProfile` is referenced in only these places — there is no persistence layer
to migrate:

```text
src/wherewolf/domain/models.py:127          definition
src/wherewolf/domain/__init__.py:12,25      re-export
src/wherewolf/execution/registry.py:28,247  construction from SUMMARIZE
src/wherewolf/desktop/widgets/schema_panel.py:24,229,297-316  rendering
tests/test_catalog_service.py:176
tests/test_models.py:127
tests/test_schema_panel.py:102
tests/test_main_window.py:1823,1837,1939,1953
```

Only `avg` is rendered today (`schema_panel.py:312`, the `Mean` column);
`std`/`q25`/`q50`/`q75` are carried but never displayed.

**Slug used throughout this plan:** `catalog-elide-temporal-profile`

---

## Orchestration Contract

**Slug:** `catalog-elide-temporal-profile`

**Plan file:**

```text
docs/plans/2026-08-10_catalog-elide-temporal-profile.md
```

**Implementation branch:**

```text
feat/catalog-elide-temporal-profile
```

**Round-complete marker:**

```text
/tmp/wherewolf/catalog-elide-temporal-profile_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/catalog-elide-temporal-profile_finalized
```

**Review notes:**

```text
docs/review/catalog-elide-temporal-profile-review-*.md
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
git checkout -b feat/catalog-elide-temporal-profile
```

Commit this plan first:

```bash
git add docs/plans/2026-08-10_catalog-elide-temporal-profile.md
git commit -m "docs(plan): add catalog-elide-temporal-profile implementation plan"
```

---

## Implementation Tasks

Four atomic tasks, in order. Each is one behaviour change, its own tests, its own
commit. TDD: write the failing test first, **record the actual failure output in
the session log**, then implement.

### Round boundaries — one task per round

This plan is reviewed task by task. A "round" in the orchestration contract below
means **exactly one task**, not the whole plan.

After finishing each task:

1. run the quality gates listed under `## Quality Gates`;
2. commit the task's code and tests;
3. run `scripts/orchestration/mark-finished catalog-elide-temporal-profile`;
4. exit cleanly and wait. Do not start the next task.

The orchestrator writes a review note per round. When it says
`STATUS: CHANGES_REQUESTED`, address it against the task just completed and
re-mark the round. Only when a note approves the current task do you clear the
marker and begin the next one. Four tasks means at least four rounds.

Do not batch tasks. A round that contains two tasks' commits must be split before
it is marked finished.

**Review-note semantics — this overrides `## Approval Handling` below.**

This project runs the orchestrator in `final` approval mode, so **you will never
receive a `STATUS: APPROVED` note.** Do not wait for one, and do not run
`scripts/orchestration/finalize`. Integration of this branch is the orchestrator's
job, performed after the last round.

Every review note you receive will end with:

```text
STATUS: CHANGES_REQUESTED
```

Each note states, near the top, whether the task just completed was **accepted**.
Act on that line:

- **"Task N accepted — proceed to Task N+1"**: run
  `scripts/orchestration/clear-finished catalog-elide-temporal-profile`, commit the
  review note if it is not already committed, apply any additional findings the note
  lists, and begin the next task.
- **No acceptance line, or findings against the current task**: the task is not
  accepted. Fix it in place, re-run the gates, re-commit, and re-mark the round.
  Do not advance.

After Task 4's round and the `## Verification` section, mark the round complete and
exit. The orchestrator takes it from there. If a note is ambiguous about which task
it refers to, treat it as referring to the task whose commits were in the round just
marked finished, and say so in the session log.

### Standing rules

- Every command that touches project tooling goes through `./run.sh`, per
  `CLAUDE.md` §5. Never invoke `uv`, `pytest`, `ruff`, or `ty` bare.
- Every test must assert **what the user sees or what a caller receives** — the
  text rendered in a cell, the value on a returned `ProfileResult`. A test that
  only asserts a field was assigned on a dataclass proves nothing.
- Qt tests run headless; follow the existing pattern in `tests/test_catalog_dock.py`
  and `tests/test_schema_panel.py` for constructing widgets under the offscreen
  platform. Do not introduce a new Qt fixture style.
- Run `scripts/check_cache_budget.sh` after each task and record the byte count in
  the session log.
- Do not touch `_as_int`. `approx_unique` and `count` come back as `BIGINT` and
  `null_percentage` as `DECIMAL`; all three are always numeric and are out of
  scope.

---

### Task 1 — Elide the File column in the middle

`CatalogDock.__init__` (`src/wherewolf/desktop/widgets/catalog_dock.py:46-58`)
leaves `textElideMode` at Qt's `ElideRight` default. Set it to
`Qt.TextElideMode.ElideMiddle` on `self._view` so the basename survives elision.

Do not change what `CatalogModel.data` returns. The display text stays the full
absolute path and the `ToolTipRole` at `catalog_model.py:79` stays as is.

**Failing test first** (`tests/test_catalog_dock.py`): build a `CatalogDock` over a
`CatalogService` holding two entries that share a long directory prefix and differ
only in basename, e.g.

```text
/very/long/shared/prefix/directory/segments/customers.parquet
/very/long/shared/prefix/directory/segments/loans.parquet
```

Assert on the **elided text the view will actually paint**, computed the way Qt
computes it:

```python
fm = QFontMetrics(view.font())
shown = fm.elidedText(path, view.textElideMode(), header.sectionSize(1) - 8)
```

The assertions: at the default section width the two rows produce **different**
strings, and each contains its own basename (`customers.parquet`,
`loans.parquet`). Under the current `ElideRight` code both strings are identical
and contain neither basename — that is the red state, and the failure message must
show both identical strings.

Also assert `view.textElideMode() == Qt.TextElideMode.ElideMiddle` so the mode is
pinned against a future default change.

Commit: `fix(catalog): elide the File column in the middle`.

---

### Task 2 — Let the File column use the available width

`CatalogDock` configures no resize behaviour, so all four columns sit at Qt's
100 px default regardless of dock width. Follow the precedent already set in
`src/wherewolf/desktop/widgets/history_dock.py:54-56` and
`src/wherewolf/desktop/widgets/schema_panel.py:86-87`.

On the catalog view's horizontal header:

- give the File column (logical index 1) `QHeaderView.ResizeMode.Stretch` so it
  absorbs the width the fixed columns do not need;
- size `Alias`, `Format`, and `Schema status` with
  `QHeaderView.ResizeMode.Interactive` and leave them user-resizable;
- keep the existing `setSectionsMovable(True)`.

`Stretch` makes the File column non-interactive by design. That is the accepted
trade: the user's complaint is that resizing does not help, and after Task 1 the
basename is visible at every width. If review disagrees, it will say so.

**Failing test first** (`tests/test_catalog_dock.py`): show a `CatalogDock` at a
known width, process events, and assert `header.sectionResizeMode(1)` is `Stretch`
and that `header.sectionSize(1)` is **strictly greater** than the sum of the other
three sections' default sizes is not required — instead assert `sectionSize(1)`
grows when the widget is widened:

```python
dock.resize(400, 200); app.processEvents(); narrow = header.sectionSize(1)
dock.resize(900, 200); app.processEvents(); wide = header.sectionSize(1)
assert wide > narrow
```

Under the current code `narrow == wide == 100`; the failure message must print
both numbers.

Commit: `fix(catalog): stretch the File column to the available width`.

---

### Task 3 — Carry profile statistics as text

Widen the five statistic fields on `ColumnProfile`
(`src/wherewolf/domain/models.py:135-139`) from `float | None` to `str | None`:
`avg`, `std`, `q25`, `q50`, `q75`. Leave `min`, `max`, `approx_unique`, `count`,
and `null_percentage` exactly as they are.

This task is plumbing only — it must not change `registry.py`. `_as_float` still
runs there and still crashes on temporal columns after this task; Task 4 fixes
that. Keeping them separate is deliberate: this task proves the type widening is
behaviour-preserving for numeric columns on its own.

Update the one render site, `schema_panel.py:312`:

```python
str(profile.avg) if profile and profile.avg is not None else "",
```

`avg` is already text, so the `str()` wrapper is now redundant — drop it, keeping
the `is not None` guard.

Update every existing `ColumnProfile(...)` construction listed under **Blast
radius** in `## Context` to pass strings for those five fields. Do not change what
those tests assert about rendered output: `avg=1.5` becoming `avg="1.5"` must still
render the cell text `1.5`. If any assertion has to change, that is a signal you
broke something — stop and say so in the session log rather than editing the
expectation.

**Failing test first** (`tests/test_schema_panel.py`): a `ColumnProfile` whose
`avg` is the string `"2024-01-01 06:56:39.5"` renders that exact text in the
`Mean` cell of `_table_widget`. Under the current `float | None` typing plus the
`str()` wrapper this cannot be expressed, and `./run.sh uv run ty check src/`
rejects it — record whichever failure you hit first, the test failure or the type
error.

Then re-run `./run.sh uv run ty check src/` and confirm it passes with the widened
type. Record the output.

Commit: `refactor(domain): carry profile statistics as text`.

---

### Task 4 — Stop coercing SUMMARIZE statistics to float

In `_DuckDBAdapter.profile_dataset` (`src/wherewolf/execution/registry.py:246-260`),
switch `avg`, `std`, `q25`, `q50`, `q75` from `_as_float` to `_as_text`.

Leave `null_percentage=_as_float(row[11])` alone — it is `DECIMAL` and always
numeric. `_as_float` therefore stays in the module and stays used; do not delete
it.

**Failing test first** (`tests/test_profile_worker.py` or a new
`tests/test_profile_temporal.py` — pick one and say which in the session log):
drive the real `_DuckDBAdapter.profile_dataset` over a real DuckDB-typed temporal
column. Build the fixture in `tmp_path`, small — 100 rows is enough, size is not
the trigger:

```python
con.execute(
    f"""
    COPY (
        SELECT
            strftime(TIMESTAMP '2024-01-01' + INTERVAL (i) SECOND,
                     '%Y-%m-%d %H:%M:%S') AS event_ts,
            i AS amount
        FROM range(100) t(i)
    ) TO '{csv_path}' (HEADER, DELIMITER ',')
    """
)
```

Assert on the returned `ProfileResult`:

- `result.error_type is None` and `result.error_message is None`;
- `result.profiles` has one entry per column, and the `event_ts` entry's
  `data_type` is `TIMESTAMP` — if it comes back `VARCHAR` the fixture is not
  exercising the bug and the test must fail loudly saying so, because a `VARCHAR`
  column returns `NULL` quantiles and would pass vacuously;
- the `event_ts` entry's `avg`, `q25`, `q50`, `q75` are non-empty strings starting
  with `2024-01-01`;
- the `amount` entry's `avg` is the numeric text `49.5`, proving numeric columns
  did not regress.

Under the current code this fails with
`could not convert string to float: '2024-01-01 ...'` surfaced as
`error_type == "ValueError"` and `profiles == ()`. Record that exact message.

Commit: `fix(profile): keep temporal SUMMARIZE statistics instead of failing`.

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

Standards: `references/verification-standards.md` in the
`orchestration-plan-author` skill. Report **output**, not conclusions — paste the
tallies and the failure text, never "confirmed passing".

Run this section on the final round, after Task 4's tests are green. Steps V1–V4
deliberately break the implementation to prove the gates can fail; V5 is the
negative control and must run last.

Every mutation is reverted with `git checkout -- <file>`, which is safe only
because each task is already committed. Before starting, confirm that:

```bash
set -o pipefail
git status --porcelain
```

prints nothing. If it prints anything, stop — a mutation revert would destroy
uncommitted work.

### V1 — Elide mode mutation (Task 1)

Change `ElideMiddle` back to `Qt.TextElideMode.ElideRight` in
`src/wherewolf/desktop/widgets/catalog_dock.py`, then:

```bash
set -o pipefail
./run.sh uv run pytest tests/test_catalog_dock.py -x
status=$?
git checkout -- src/wherewolf/desktop/widgets/catalog_dock.py
echo "V1 pytest exit: $status"
```

Expected: non-zero exit, and the failure output names the two identical elided
strings. Record the assertion message verbatim. If the exit status is 0, the Task 1
test is not testing elision — fix the test, not the mutation.

### V2 — Stretch mode mutation (Task 2)

Delete the `setSectionResizeMode(1, ...Stretch)` line from `catalog_dock.py`, then
repeat the V1 command block. Expected: non-zero exit, with the failure printing the
narrow and wide section sizes as equal (both `100`). Revert, and record the
message.

### V3 — Float coercion mutation (Task 4)

Change `avg=_as_text(row[5])` back to `avg=_as_float(row[5])` in
`src/wherewolf/execution/registry.py`, then:

```bash
set -o pipefail
./run.sh uv run pytest -k "temporal or profile" -x
status=$?
git checkout -- src/wherewolf/execution/registry.py
echo "V3 pytest exit: $status"
```

Expected: non-zero exit, and the reported error is
`could not convert string to float: '2024-01-01...'`. Record it. An exit status of
0 means the Task 4 fixture is not producing a `TIMESTAMP` column — a `VARCHAR`
column returns `NULL` quantiles and passes vacuously. Fix the fixture.

### V4 — Fixture-type guard

Prove the Task 4 test's own precondition check is live. Change the fixture's
`event_ts` expression so DuckDB keeps it as text — wrap it so the sniffer cannot
promote it, e.g. prefix each value with `ts=`. Re-run the Task 4 test.

Expected: the test fails on the `data_type == "TIMESTAMP"` assertion, not on the
statistics assertions. Record which assertion fired. If it instead *passes*, the
guard is decoration and the whole Task 4 test is unreliable. Revert the fixture.

### V5 — Negative control (runs last)

With every mutation reverted and the tree clean:

```bash
set -o pipefail
git status --porcelain
./run.sh uv run ruff check .
./run.sh uv run ty check src/
./run.sh uv run pytest
scripts/check_cache_budget.sh
```

Record: the `git status --porcelain` output (must be empty), the ty result line,
the pytest `passed`/`failed`/`error` tallies, and the cache byte count. This step
passes only if the implementation actually works, and it runs after V1–V4 so it
cannot pass merely because nothing was exercised.

### V6 — Repository cleanliness

```bash
set -o pipefail
git ls-files --others --exclude-standard
find . -path ./.git -prune -o -name '__pycache__' -print -o -name '.pytest_cache' -print
```

Expected: no untracked files, and no cache directories inside the repository per
`CLAUDE.md` §5. Paste both outputs. Non-empty output is a failure, not a note.

### Explicitly deferred / not verified

State each of these in the session log; an unstated gap reads as a covered one.

- **No GUI was launched.** All Qt verification is headless and asserts on
  `QFontMetrics.elidedText` and header section sizes. Nobody has looked at the real
  window. Whether `ElideMiddle` plus a stretched File column *looks* right in the
  running app is unverified, and the user should check it against
  `fix/Screenshot_20260802_132729.png`.
- **The `str()` removal at `schema_panel.py:312` is not mutation-tested.**
  `str()` on a `str` is the identity function, so reverting it changes no observable
  behaviour and no test can catch it. It is a readability change only.
- **`std`, `q25`, `q50`, `q75` are still not rendered anywhere.** Task 3 and Task 4
  make them carry correct values, but `SchemaPanel` displays only `Mean`. Surfacing
  the quartiles is out of scope for this plan.
- **Only `TIMESTAMP` is covered end to end.** `DATE`, `TIME`, and
  `TIMESTAMP WITH TIME ZONE` were measured to fail the same way but are not
  separately tested. Say so rather than implying full temporal coverage.
- **Windows paths are not exercised on Windows.** Defect A was reported with a
  `C:\...` path; the tests use POSIX fixtures. The elision logic is
  platform-independent, but the path separators in the fixtures are not.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished catalog-elide-temporal-profile
```

This writes:

```text
/tmp/wherewolf/catalog-elide-temporal-profile_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer catalog-elide-temporal-profile`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/catalog-elide-temporal-profile-review-*.md
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
   scripts/orchestration/clear-finished catalog-elide-temporal-profile
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
   git add docs/review/catalog-elide-temporal-profile-review-*.md
   git commit -m "docs(review): record catalog-elide-temporal-profile review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished catalog-elide-temporal-profile
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer catalog-elide-temporal-profile` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed catalog-elide-temporal-profile
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize catalog-elide-temporal-profile
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/catalog-elide-temporal-profile_finalized
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
scripts/orchestration/finalize catalog-elide-temporal-profile
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/catalog-elide-temporal-profile_finished
/tmp/wherewolf/catalog-elide-temporal-profile_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
