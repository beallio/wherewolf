# Plan: Theme in preferences, sortable history, dock restore, filters and export placement (ui-refinements)

## Context

Seven refinements requested against build `f7bc33d`. Each was checked against the code
before this plan was written.

An eighth request — tabbed multiple queries, each with its own result section — is
**deliberately not in this plan**. It restructures the central widget and the execution
controller, needs its own session model, and would collide with almost every task below.
It is planned separately as `multi-query-tabs` and should run after this round merges.

### R1 — editor theme belongs in Preferences

`main_window.py:310` puts `editor_theme_selector` on the toolbar. It is a set-once
preference, not a per-query control, and it competes for the toolbar space that the
frequently-used controls need.

### R2 — history is not sortable

`widgets/history_dock.py` never calls `setSortingEnabled`. There is no way to order by
timestamp or query text; rows appear in storage order only.

### R3 — closed docks cannot be reopened individually

The View menu (`main_window.py:860-869`) offers Reset Layout, Clear Preview Filter, Show
Hidden Files and Preferences. Close the History dock and the only route back is resetting
the whole layout, discarding every other adjustment. `QDockWidget.toggleViewAction()`
exists precisely for this and is not used.

### R4 — alternating row colours are inconsistent

Only history has them (`history_dock.py:25`). The catalog and the schema/profile table do
not, and the profile table is now nine columns wide, which is exactly where row banding
earns its keep.

### R5 — result columns do not show their type

The results grid shows names only. The schema panel knows the types, but while reading
results a user has to look away to answer "is this column text or a number" — which also
determines whether sorting will behave the way they expect.

### R6 — export controls are far from the results

`main_window.py:237-239` puts Export Preview / Export Full / Export Selection on the
toolbar, and `main_window.py:285` puts the format selector there too — while the thing
being exported lives in the results tab at the other end of the window. There is also no
plain "Export" button beside the results themselves.

### R7 — the preview filter is substring-only

`models/typed_sort_proxy_model.py:24` lowercases the text and matches it as a substring.
Typing `age > 40` filters to rows whose text literally contains `age > 40`, which is never
what anyone means.

**Slug used throughout this plan:** `ui-refinements`

---

## Orchestration Contract

**Slug:** `ui-refinements`

**Plan file:**

```text
docs/plans/2026-08-02_ui-refinements.md
```

**Implementation branch:**

```text
feat/ui-refinements
```

**Round-complete marker:**

```text
/tmp/wherewolf/ui-refinements_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/ui-refinements_finalized
```

**Review notes:**

```text
docs/review/ui-refinements-review-*.md
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
git checkout -b feat/ui-refinements
```

Commit this plan first:

```bash
git add docs/plans/2026-08-02_ui-refinements.md
git commit -m "docs(plan): add ui-refinements implementation plan"
```

---

## Implementation Tasks

One commit per task. TDD: failing test first. Tests reach the feature from `MainWindow` as
a user would, and assert `isVisible()` where visibility is the point — a control that
exists but is hidden has shipped from this repo before.

### Task 1 — move the editor theme to Preferences (R1)

Remove `editor_theme_selector` from the toolbar; add the same control to the Preferences
dialog beside the completion and profiling settings. The persisted key and its default must
not change — an existing user's chosen theme must survive the move.

Test that the toolbar no longer carries the control, that Preferences does, and that a
theme saved before the move is still applied. That last assertion is the one that catches a
silent settings-key rename.

### Task 2 — sortable history (R2)

Enable sorting on the history table, with a sensible default (newest first) and a visible
sort indicator. Timestamps must sort chronologically, **not lexically** — the displayed text
is second-truncated ISO, so verify with timestamps that would sort differently as strings
than as instants.

Test that clicking the timestamp header reverses the order, and that a set of timestamps
crossing a boundary where string and chronological order differ sorts correctly.

### Task 3 — reopen closed docks from the View menu (R3)

Add each dock's `toggleViewAction()` to the View menu, above Reset Layout, with a separator.
The action text should name the dock. Closing a dock and re-triggering its action must
restore it without disturbing the other docks' geometry.

Test: close a dock, assert it is hidden, trigger its View-menu action, assert it is visible
again, and assert a second dock's visibility was untouched.

### Task 4 — consistent alternating row colours (R4)

Enable alternating row colours on the catalog table and the schema/profile table to match
history. Confirm the alternate colour is legible against the active editor theme rather than
hardcoding a shade — this repo has already shipped one invisible-text defect from a
hardcoded near-white.

Test that all three views report `alternatingRowColors()` true, and assert the alternate
base colour differs measurably in luminance from the text colour.

### Task 5 — data-type icons on result column headers (R5)

Show a small type indicator on each result column header: numeric, text, temporal, boolean,
other. Derive the family from the Polars dtype the results model already holds.

Generate the icons at runtime (a `QPixmap` per family) rather than adding asset files, and
colour them from the palette so they work in both themes. The full dtype goes in the header
tooltip.

Test that a frame with an integer, a string, a date and a boolean column yields four
distinct non-null header icons, and that the tooltip names the actual dtype. Assert the
icons differ from each other — four identical icons would pass a naive "icon is not null"
check.

### Task 6 — move export controls to the results section (R6)

Move Export Preview / Export Full / Export Selection and the format selector out of the
toolbar into the results tab, beside the preview filter. Add a clear **Export** button that
performs the export with the currently selected format and scope.

The actions must remain in the Query menu so keyboard shortcuts and menu access still work —
moving a control must not remove the only route to it.

Test that the results page exposes the export controls and that they are visible at 1024px
width, that the menu actions still exist, and that pressing Export with Parquet selected
writes a readable Parquet file. Assert on the artifact, not on the call arguments.

### Task 7 — SQL expressions in the preview filter (R7)

Let the filter accept a SQL predicate over the previewed frame — `age > 40`,
`region = 'East' AND amount > 100`. Keep plain text working as a substring search, so the
box stays useful for "find this word".

Implementation: DuckDB already reads Polars frames natively and is already a dependency, so
evaluate the predicate as `SELECT * FROM frame WHERE <expr>` against an in-memory
connection over the preview frame. Decide expression-vs-substring by attempting to parse as
a predicate and falling back on failure — do not require the user to prefix or quote
anything.

A malformed expression must show an inline, non-blocking error and leave the previous rows
visible. It must never raise into the UI thread or clear the grid.

Test: `age > 40` on a fixture with known ages returns exactly the expected row count; a
plain word still substring-matches; `age >` (malformed) shows an error and leaves the row
count unchanged; and a predicate naming a non-existent column reports that clearly.

### Cross-cutting requirements

- Do not weaken, skip or delete existing tests.
- Do not change persisted settings keys or their defaults except where a task says so.
- Do not remove `timid = true`, the `pyarrow` import, or the overwrite confirmation.
- Do not change `EngineKind` or the sqlglot identifiers in `DIALECT_MAPPING`.
- Do not reintroduce a `QScrollArea` in the toolbar.
- Do not bump the version, tag, or touch `main`.
- Run `./run.sh uv run ty check .` (whole repo) before committing.

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

```bash
./run.sh uv run ruff check . && ./run.sh uv run ruff format --check .
./run.sh uv run ty check .
./run.sh uv run pytest
```

Record in the session log:

1. Toolbar control list before and after the theme move, and the theme applied after a
   settings round-trip.
2. History order before and after clicking the timestamp header, using timestamps whose
   string and chronological order disagree.
3. A dock's `isVisible()` across close → View-menu toggle → reopen, plus a sibling dock's
   visibility throughout.
4. `alternatingRowColors()` for history, catalog and schema, and the luminance gap between
   the alternate base and the text colour.
5. The four header icons for an int/str/date/bool frame, shown to be distinct, with tooltips.
6. Export controls visible at 1024px; the row count and first rows of a Parquet file written
   by the new Export button.
7. Filter results for `age > 40`, a plain word, a malformed expression, and an unknown
   column — with the row count in each case and the error text where applicable.

**Negative controls are mandatory for tasks 2, 3, 5, 6 and 7**, run against the **full**
suite. Confirm each mutation actually modified the file before trusting its result: several
times in this project a mutation that failed to apply looked exactly like a guard that does
not bite, and one targeted the wrong thing entirely. If a mutation reports no failures,
first prove it changed the code.

## Deferred

Tabbed multiple queries is out of scope here and planned as `multi-query-tabs`.

Icon legibility at high DPI, the visual weight of row banding, and toolbar composition after
the export controls move are manual maintainer checks. Filter expressions are evaluated
against the **preview** frame only, not the full result set — a predicate cannot reach rows
the preview limit excluded, and that boundary should be stated in the UI copy.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished ui-refinements
```

This writes:

```text
/tmp/wherewolf/ui-refinements_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer ui-refinements`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/ui-refinements-review-*.md
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
   scripts/orchestration/clear-finished ui-refinements
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
   git add docs/review/ui-refinements-review-*.md
   git commit -m "docs(review): record ui-refinements review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished ui-refinements
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer ui-refinements` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed ui-refinements
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize ui-refinements
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/ui-refinements_finalized
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
scripts/orchestration/finalize ui-refinements
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/ui-refinements_finished
/tmp/wherewolf/ui-refinements_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
