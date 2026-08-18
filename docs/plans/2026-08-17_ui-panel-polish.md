# Plan: Result summary strip, schema panel filter, and value counts polish (ui-panel-polish)

## Context

Three independent UI quality-of-life defects, drawn from
`feature-ideation-ui-quality-of-life.md` items 4, 9, and 10. All three are read-side
polish in panels that already exist; none of them changes query execution, storage, or
the catalog. This is the first of three sequenced plans — `workspace-persistence` and
`query-workspaces` follow and depend on this one being merged, so keep the scope here
strictly to the three units below.

### Defect A — the result summary disappears after ten seconds

`src/wherewolf/desktop/main_window.py:622-632` builds a genuinely useful summary:

```python
msg = (
    f"Engine: {engine_name} | State: Succeeded | Elapsed: {result.execution_seconds:.2f}s | "
    f"Preview Rows: {result.preview_row_count}{trunc_str}"
)
self._show_status(msg, 10000)
```

It goes to the status bar with a 10 000 ms timeout and then vanishes. A user who runs a
query, scrolls results for a minute, and then asks "how many rows was that, and was it
truncated?" has to re-run the query to find out. The truncation flag is the serious
part: it is a correctness signal about whether the user is looking at all their data,
and it is currently transient.

`result.truncated`, `result.preview_row_count`, `result.total_row_count`, and
`result.execution_seconds` are all already on the result object
(`src/wherewolf/domain/models.py:91-92`); nothing new needs computing.

### Defect B — the schema panel is unusable on long paths and wide tables

Two problems in `src/wherewolf/desktop/widgets/schema_panel.py`:

1. `:273-275` interpolates the full absolute path into a single status label:

   ```python
   f"{alias} — {self._entry.path} ({self._entry.source_format.value}) — {len(columns)} columns"
   ```

   and then appends up to four more clauses onto the same label (`:276-289`: skipped
   reason, stale profile, profiling error, "Profiling..."). The label is
   `setWordWrap(True)` (`:66`), and Windows paths contain almost no spaces to break on,
   so it wraps badly and pushes the actual schema table down. This is the same root
   cause as the catalog File column defect fixed in `filename-and-value-counts-ux`:
   the full path is being displayed where the filename is what identifies the row.

2. `self._table_widget` is a 9-column `QTableWidget` (`:70-84`) with no filter. On a
   200-column Parquet file, finding one column means scrolling.

### Defect C — the value-counts window wastes its space

`src/wherewolf/desktop/widgets/value_counts_window.py:151-181`, after the scrolling fix
that already landed:

- The table and the chart scroll area are stacked in a fixed `QVBoxLayout` with no
  splitter, so the user cannot trade space between them.
- `self.table` is a `_CopyTableWidget` with sorting never enabled, so there is no way to
  sort by count ascending — usually the more interesting end when hunting data-quality
  problems (rare values, typos, unexpected nulls).
- The only way data leaves the window is clipboard TSV via `serialize_table_widget_to_tsv`,
  even though the project has a complete export subsystem
  (`src/wherewolf/desktop/export_controller.py`, `src/wherewolf/services/preview_export.py`).

### Intended outcome

- Result metadata stays on screen until the next query replaces it.
- The schema panel identifies its dataset by filename with the full path on hover, keeps
  warning clauses off the identity line, and can filter columns by name.
- The value-counts window has a user-adjustable splitter, a sortable table, and an
  export button.

### Design decisions already made

Settled with the user; do not revisit.

- Plan A covers items 4, 9, and 10 only. Catalog persistence, editor drafts, history
  search, editor tabs, and the saved-query library are explicitly out of scope and are
  covered by the two follow-on plans.
- The schema panel keeps a single status label for identity; warning clauses move to a
  **separate** label so a long warning never pushes the dataset name around.

**Slug used throughout this plan:** `ui-panel-polish`

---

## Orchestration Contract

**Slug:** `ui-panel-polish`

**Plan file:**

```text
docs/plans/2026-08-17_ui-panel-polish.md
```

**Implementation branch:**

```text
feat/ui-panel-polish
```

**Round-complete marker:**

```text
/tmp/wherewolf/ui-panel-polish_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/ui-panel-polish_finalized
```

**Review notes:**

```text
docs/review/ui-panel-polish-review-*.md
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
git checkout -b feat/ui-panel-polish
```

Commit this plan first:

```bash
git add docs/plans/2026-08-17_ui-panel-polish.md
git commit -m "docs(plan): add ui-panel-polish implementation plan"
```

---

## Implementation Tasks

Each task below is **atomic**: one coherent behavior change, its own failing test first,
its own commit, and independently verifiable. Do not batch two tasks into one commit.
Run `scripts/orchestration/run-quality-gates` before each commit, not just at the end.

Units are ordered A → B → C. Finish and commit a unit before starting the next.

### Unit A — Persistent result summary strip

**A1. Add the summary widget.** *(one commit)*

In `src/wherewolf/desktop/main_window.py`, in the results page construction around
`:892-906`, add a `QLabel` named `result_summary_label` (set `setObjectName("result_summary_label")`)
between the sort notice and the results table. Start it empty and hidden.

Test first in `tests/test_main_window.py`: the label exists, has that object name, and
is hidden before any query runs.

**A2. Populate it on every terminal query state.** *(one commit)*

Add a `_set_result_summary(text: str)` helper that sets the text and shows the label
when text is non-empty, hides it when empty. Call it from all three branches at
`:622-640`:

- Succeeded: `Engine · N rows · X.XXs` plus `· truncated at N preview rows` when
  `result.truncated`. When `result.total_row_count` is not `None` and differs from
  `preview_row_count`, render `showing N of M rows`.
- Failed: `Engine · failed after X.XXs`.
- Cancelled: `Engine · cancelled after X.XXs`.

Clear the label at the start of a new run so a stale summary never sits over fresh
results.

Keep the existing `self._show_status(...)` calls exactly as they are. This task adds a
surface; it does not remove one.

Test first: drive a succeeded result with `truncated=True` and assert the label text
contains the row count, the elapsed time, and the word `truncated`; drive a failed
result and assert the label reports failure; assert the label is cleared when a new run
starts. At least one assertion must fail if `_set_result_summary` is never called.

### Unit B — Schema panel

**B1. Split identity from warnings in the status label.** *(one commit)*

In `src/wherewolf/desktop/widgets/schema_panel.py`:

- Change the identity string at `:273-275` to use `self._entry.path.name` instead of
  `self._entry.path`, and set the full path via `self._status_label.setToolTip(str(self._entry.path))`.
- Add a second `QLabel` (`self._warning_label`, `setObjectName("schema_warning_label")`,
  word-wrapped) directly beneath `_status_label`. Move the four appended clauses at
  `:276-289` — `profile_skipped_reason`, the stale-profile notice, the profiling error,
  and `Profiling...` — onto that label instead of concatenating them onto
  `_status_label`. Hide the warning label when it has no text.

`status_text()` at `:160` currently returns `self._status_label.text()` and is used by
tests. Keep it returning the identity line only, and add a `warning_text()` accessor for
the new label. Existing tests in `tests/test_schema_panel.py` that assert warning
clauses appear in `status_text()` must be repointed at `warning_text()` — this change is
**required by this plan**, so it is not a scope violation, but do not weaken what any of
them assert. If an assertion cannot be preserved, stop and say so in the session log.

Test first: with an entry whose path is long, `status_text()` contains the basename and
does **not** contain the parent directory, and the tooltip is the full path. With a
stale profile plus a skipped reason, both clauses appear in `warning_text()` and neither
appears in `status_text()`.

**B2. Filter the column table by name.** *(one commit)*

Add a `QLineEdit` (`self.column_filter`, `setObjectName("schema_column_filter")`,
placeholder `Filter columns`) between the status/warning labels and `_table_widget`.
On `textChanged`, hide rows whose column-name cell (column 0) does not contain the
filter text, case-insensitively, using `self._table_widget.setRowHidden(row, hidden)`.

Re-apply the filter whenever the table is repopulated in `_update_view`, or a filter
typed before a dataset loads will silently stop applying.

Test first: populate a schema with several columns, type a filter matching one, and
assert exactly the matching rows are visible via `isRowHidden`. Then repopulate the
table with the filter still set and assert the filter is still applied — that second
assertion is the one that catches forgetting to re-apply.

### Unit C — Value-counts window

**C1. Splitter between table and chart.** *(one commit)*

In `src/wherewolf/desktop/widgets/value_counts_window.py`, replace the direct
`layout.addWidget(self.table)` / `layout.addWidget(self.chart_scroll_area)` with a
vertical `QSplitter` (`self.content_splitter`) holding both, added to the layout.
Keep `self.table`, `self.chart`, and `self.chart_scroll_area` as attributes pointing at
the same objects — existing tests use all three.

Test first: `content_splitter.count() == 2`, both children are the table and the scroll
area, and after `setSizes([100, 400])` the reported sizes differ from
`setSizes([400, 100])`. A fixed `QVBoxLayout` cannot satisfy that.

**C2. Sortable value table.** *(one commit)*

Enable sorting on `self.table`. The Count and Percentage columns must sort **numerically**,
not lexically — with plain `QTableWidgetItem` text, `100` sorts before `9`. Populate
the numeric cells with `QTableWidgetItem` instances whose `Qt.ItemDataRole.EditRole`
data is set to the `int`/`float` value via `setData`, so Qt compares numbers.

Note `_on_result` at `:188-195` rebuilds rows on every result; call
`self.table.setSortingEnabled(False)` before repopulating and re-enable it afterwards,
or rows will reshuffle mid-population.

Test first: load counts whose lexical and numeric orders differ (e.g. counts 9, 100, 25),
sort ascending on the Count column, and assert the visible order is 9, 25, 100. That
test fails against lexical sorting, which is the whole point.

**C3. Retain the last result on the window.** *(one commit)*

`_on_result` currently consumes the `ValueCountsResult` into the table and chart and
keeps no reference, so there is nothing for an export to read. Store it as
`self._last_result: ValueCountsResult | None`, set on success and cleared to `None` on
the error branch.

This is separated from C4 deliberately: C4 cannot be written or tested without it, and
bundling them would make one commit that does two things.

Test first: `_last_result` is `None` before any result, holds the counts after a
successful result, and returns to `None` after an error result.

**C4. Export the value counts.** *(one commit)*

Add an `Export…` `QPushButton` to the controls row, enabled only when `_last_result` is
not `None`.

The file-dialog layer must be extended — `src/wherewolf/desktop/dialogs/file_dialog_service.py`
currently exposes only `choose_dataset_files`, `choose_export_path`, and
`choose_history_sql_path` (`:26-124`). Add `choose_value_counts_path(default_directory, export_format, parent=None) -> Path | None`
to **all three** of `FileDialogService` (the `Protocol` at `:25`), `FakeFileDialogService`
(`:35`), and `QtFileDialogService` (`:62`). Omitting the Fake will break every test that
injects it.

Reuse `export_file_filter` and `normalise_destination` from
`src/wherewolf/services/export_destination.py` for the filter and extension handling.
Build a `polars.DataFrame` from `self._last_result.counts` with columns `value`,
`count`, `percentage`, and write it via `write_preview`
(`src/wherewolf/services/preview_export.py:14`), which takes a `pl.DataFrame`, a
destination `Path`, and an `ExportFormat`.

Offer the same format choices the rest of the app offers rather than hardcoding CSV;
take the default from `SettingsService.restore_export_format()`. Render a `None` value
as `<null>`, matching the table and chart.

Test first: with counts loaded, export to a `tmp_path` destination via
`FakeFileDialogService` and assert the written file round-trips to the same row count
and the same `count` values, including a row whose value is `None` arriving as `<null>`.
Assert the button is disabled before any result and after an error result.

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

Every step must be able to fail. Before adding a step of your own, answer: *what state
of the world makes this print the failure output?* If the answer is "none" or "only if
the tool is broken", it is decoration — delete it. Report the actual output of each
command, tallies and printed values, not a conclusion that it passed.

Qt needs an offscreen platform here:

```bash
export QT_QPA_PLATFORM=offscreen
set -o pipefail
```

**`set -o pipefail` is mandatory for every step in this section.** Without it,
`pytest ... | tail -2` reports `tail`'s exit status, so a failing suite that still prints
a summary line looks identical to a passing one. Every pipeline below relies on it. If
you run a step in a fresh shell, set it again there.

### V1 — Baseline

Record the tally on `dev` before any change, so the final count is comparable:

```bash
./run.sh uv run pytest -q; echo "pytest exit=$?"
```

Expected at time of writing: `555 passed, 7 deselected`. If the baseline differs, record
what you actually saw and continue — a differing baseline is information, not a blocker.

### V2 — Per-unit suites

Run after each unit and record both the tally **and the exit code**:

```bash
./run.sh uv run pytest tests/test_main_window.py -q;          echo "A exit=$?"
./run.sh uv run pytest tests/test_schema_panel.py -q;         echo "B exit=$?"
./run.sh uv run pytest tests/test_value_counts_window.py -q;  echo "C exit=$?"
```

A non-zero exit is the authoritative signal. Do not report a unit as passing on the
strength of a summary line alone.

### V3 — Prove the numeric sort is really numeric

C2 is the task most likely to pass for the wrong reason, because lexical sorting looks
correct on small single-digit fixtures. Run this directly and record the output:

```bash
./run.sh uv run pytest tests/test_value_counts_window.py -q -k "sort" -v; echo "exit=$?"
```

The fixture must include counts whose lexical and numeric orders disagree (9, 25, 100).
If the test passes when the numeric `EditRole` data is removed, it is not testing
numeric sorting — fix the test before continuing.

### V4 — Mutation gates (negative controls)

These run **after** V1–V3. For each: apply the mutation, run the named suite, record
that it goes **red**, revert, confirm green again. A mutation that leaves the suite green
means that task is untested — fix the test, do not move on.

| # | Mutation | Suite that must go red |
|---|---|---|
| 1 | In `main_window.py`, make `_set_result_summary` a no-op body (`return`) | `tests/test_main_window.py` |
| 2 | In `main_window.py`, drop the `truncated` clause from the summary text | `tests/test_main_window.py` |
| 3 | In `schema_panel.py`, use `self._entry.path` instead of `.name` in the identity line | `tests/test_schema_panel.py` |
| 4 | In `schema_panel.py`, skip re-applying the column filter in `_update_view` | `tests/test_schema_panel.py` |
| 5 | In `value_counts_window.py`, remove the numeric `setData(EditRole, ...)` calls | `tests/test_value_counts_window.py` |
| 6 | In `value_counts_window.py`, replace the `QSplitter` with the old `QVBoxLayout` adds | `tests/test_value_counts_window.py` |
| 7 | In `value_counts_window.py`, stop clearing `_last_result` on the error branch | `tests/test_value_counts_window.py` |
| 8 | In `value_counts_window.py`, hardcode CSV instead of the selected export format | `tests/test_value_counts_window.py` |

Mutation 2 exists specifically because the truncation flag is the correctness-relevant
part of the summary and is the easiest clause to lose in a refactor.

### V5 — Full gates

```bash
scripts/orchestration/run-quality-gates
git status --short
```

Record the ruff, ty, and pytest tallies as printed, and confirm the tree is clean.

### Deferred and unverified

State these in the session log; an unstated gap reads as a covered one.

- **No pixel or visual verification.** Every assertion is on widget state (text,
  visibility, hidden rows, splitter sizes), not on rendered output. A stylesheet or
  theme that made the new summary strip or warning label invisible would not be caught.
- **Light/dark theming of the new widgets is not asserted.** The new labels and button
  inherit the palette; no test checks contrast in either mode.
- **Export is verified through the service layer, not the file dialog.** The save-dialog
  interaction in C3 is monkeypatched, so a broken dialog wiring would not be caught by
  the suite.
- **No Windows verification.** As with the previous round, all measurement is
  Linux/offscreen. B1 changes which string is displayed, so it is font-independent, but
  the schema panel's wrapping behavior on Segoe UI is not reproduced here.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished ui-panel-polish
```

This writes:

```text
/tmp/wherewolf/ui-panel-polish_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer ui-panel-polish`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/ui-panel-polish-review-*.md
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
   scripts/orchestration/clear-finished ui-panel-polish
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
   git add docs/review/ui-panel-polish-review-*.md
   git commit -m "docs(review): record ui-panel-polish review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished ui-panel-polish
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer ui-panel-polish` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed ui-panel-polish
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize ui-panel-polish
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/ui-panel-polish_finalized
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
scripts/orchestration/finalize ui-panel-polish
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/ui-panel-polish_finished
/tmp/wherewolf/ui-panel-polish_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
