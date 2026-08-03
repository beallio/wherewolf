# Plan: Legible line numbers, named schema, labelled controls (ui-legibility)

## Context

The maintainer ran the current build (`fix/Screenshot_20260802_132729.png`) and reported
three usability defects. All three were reproduced and **measured**, not inferred.

### U1 — line numbers are invisible because the margin is too narrow

`desktop/widgets/sql_editor.py:261`:

```python
self.setMarginWidth(0, " " * width)      # width = len(str(line_count)) + 1
```

Sizing a margin with **space** characters underestimates it badly, because digits are
much wider than spaces. Measured on the running app:

```text
margin width now : 14px
width of '999'   : 21px   <- needed for a 3-digit file
width of '  '    :  6px   <- what the code reserves
```

So the digits are clipped. This is **not** a contrast problem — the line-number style
measures a healthy 0.878 luminance delta (black on `#e0e0e0`). Do not "fix" it by
changing colours.

A secondary point: that `#e0e0e0` margin background is a light strip against the editor's
`#1e1e1e` paper, which looks wrong in the dark theme even once the digits fit.

### U2 — the schema panel does not say which dataset it describes

`desktop/widgets/schema_panel.py` sets `_status_label` to `"Schema (20 columns):"` with no
alias. The maintainer's catalog holds `customers` and `loans`; the panel gives no way to
tell which one is on screen. The empty state reads `"No table selected"`.

### U3 — toolbar controls do not say what they do

Every toolbar control has an **empty tooltip** and no caption:

```text
engine_selector              tooltip=''
input_dialect_selector       tooltip=''
export_format_selector       tooltip=''
editor_theme_selector        tooltip=''
translation_target_selector  tooltip=''
preview_limit_selector       tooltip=''
```

A bare dropdown reading `DuckDB` does not say whether it selects the execution engine or
the SQL dialect — and there are now **two dialect dropdowns and an engine dropdown**, all
unlabelled, which is worse than having none. The screenshot also shows controls running
off the right edge of the toolbar.

**Slug used throughout this plan:** `ui-legibility`

---

## Orchestration Contract

**Slug:** `ui-legibility`

**Plan file:**

```text
docs/plans/2026-08-02_ui-legibility.md
```

**Implementation branch:**

```text
feat/ui-legibility
```

**Round-complete marker:**

```text
/tmp/wherewolf/ui-legibility_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/ui-legibility_finalized
```

**Review notes:**

```text
docs/review/ui-legibility-review-*.md
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
git checkout -b feat/ui-legibility
```

Commit this plan first:

```bash
git add docs/plans/2026-08-02_ui-legibility.md
git commit -m "docs(plan): add ui-legibility implementation plan"
```

---

## Implementation Tasks

One commit per task. TDD: failing test first.

The standing rule applies — tests reach the feature from `MainWindow` as a user would.
Additionally, for this plan: **assert on measured geometry and text content, never on
colour or pixel literals.** A test pinning `#e0e0e0` would pass while the numbers stay
invisible, which is exactly how U1 shipped.

### Task 1 — line-number margin (U1)

Size margin 0 from digit glyphs, not spaces — `QFontMetrics.horizontalAdvance` over the
widest digit string the document can reach, plus padding. It must stay correct after a
font-size change (`_apply_font_size`) and as the document grows past 9, 99 and 999 lines.

Test by asserting `marginWidth(0) >= QFontMetrics(font).horizontalAdvance("9" * digits)`
for documents of 5, 50 and 500 lines, and again after changing the font size. That
inequality is the actual requirement; a hardcoded pixel expectation is not.

Then restyle the margin to sit in the dark theme rather than against it, deriving colours
from the editor paper the way the caret line already does.

### Task 2 — schema panel names its dataset (U2)

Include the alias in the panel's header, e.g. `customers — 20 columns`. Keep a sensible
empty state. Test that after loading a schema for alias `customers` the panel's visible
text contains `customers`, and that switching to `loans` updates it — the second half is
what catches a header written once and never refreshed.

### Task 3 — label the toolbar controls (U3)

Give every control a visible caption and a tooltip saying what it affects. At minimum
distinguish, in wording a user can act on:

- **engine** — where the query runs (DuckDB or Spark)
- **input dialect** — the dialect you are writing in, transpiled to the engine
- **translation target** — the dialect the Translation tab renders into
- **export format**, **editor theme**, **preview row limit**

Test that each named control has a non-empty tooltip and an associated visible caption,
driven by iterating the controls rather than by six copy-pasted assertions — a loop keeps
the guard honest when a seventh control is added.

Then address overflow so controls do not run off the right edge: let the toolbar wrap,
scroll, or move the less-used controls somewhere they fit. State in the session log which
approach you chose and why.

### Cross-cutting requirements

- Do not weaken, skip or delete existing tests.
- Do not remove `timid = true`, the `pyarrow` import, or the overwrite confirmation.
- Do not alter `DIALECT_MAPPING` or `EngineKind`.
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

1. `marginWidth(0)` and the required digit width for 5-, 50- and 500-line documents, and
   the same pair after a font-size change.
2. The schema panel's header text for two different aliases in sequence.
3. Every toolbar control's caption and tooltip, printed from a loop.
4. The overflow approach chosen, and the toolbar's `sizeHint()` versus the window width.

**Negative controls are mandatory for tasks 1 and 3.** Restore `" " * width` sizing and
confirm the margin test fails; blank one control's tooltip and confirm the labelling test
fails. Paste the failing output.

## Deferred

Whether the result *looks* right — margin styling against the dark theme, caption
placement, and the chosen overflow behaviour — is a manual maintainer check. Automated
tests here prove the digits have room and the controls carry text, not that the toolbar
is well composed. Note it in `docs/review/manual-acceptance-checklist.md`.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished ui-legibility
```

This writes:

```text
/tmp/wherewolf/ui-legibility_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer ui-legibility`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/ui-legibility-review-*.md
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
   scripts/orchestration/clear-finished ui-legibility
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
   git add docs/review/ui-legibility-review-*.md
   git commit -m "docs(review): record ui-legibility review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished ui-legibility
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer ui-legibility` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed ui-legibility
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize ui-legibility
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/ui-legibility_finalized
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
scripts/orchestration/finalize ui-legibility
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/ui-legibility_finished
/tmp/wherewolf/ui-legibility_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
