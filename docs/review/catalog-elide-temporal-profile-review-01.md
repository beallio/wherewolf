# Review — catalog-elide-temporal-profile (round 01)

Branch: `feat/catalog-elide-temporal-profile`
Reviewed against: `docs/plans/2026-08-10_catalog-elide-temporal-profile.md`
Round contents: `5da1f82` — Task 1, "Elide the File column in the middle".

## Verdict

**Task 1 is NOT accepted. Do not proceed to Task 2 yet.**

The production change is correct and is the whole of what Task 1 asked for. The
test that guards it is not, and fixing it requires amending Task 2's design — so
both are handled in this round.

Credit where due: the session log's `design_decisions` entry openly recorded the
fixture substitution and the 92-pixel budget that motivated it. That honesty is
what made this reviewable. The observation was right; the response to it was
wrong.

## Gate status

Re-run independently by the orchestrator on `5da1f82`, not taken from the session
log:

```text
./run.sh uv run pytest -q     495 passed, 7 deselected in 12.95s (90% total coverage)
./run.sh uv run ty check src/ All checks passed!
./run.sh uv run ruff check .  All checks passed!
git status --porcelain        (empty)
```

The session log's gate claims match what I measured. Cache budget 2,789,445,143
bytes is within the 4 GiB ceiling in `scripts/check_cache_budget.sh`, and
`/tmp/wherewolf` is correctly a symlink again.

## Required changes

### R1 — The Task 1 test passes at any column width, including widths where the bug is unfixed

`tests/test_catalog_dock.py::test_catalog_file_column_elides_paths_in_the_middle`
substituted `a.csv` / `b.csv` for the plan's `customers.parquet` / `loans.parquet`.
Five-character basenames fit the trailing elision budget at every width, so the
assertion cannot fail for any reason related to column sizing. It would still pass
if the File column were 20 pixels wide.

Measured with `QFontMetrics.elidedText` at the default application font, available
width in pixels (section size minus the 8 px cell padding):

| available | `a.csv` / `b.csv` | `customers.parquet` / `loans.parquet` |
|---|---|---|
| 92 (current default) | distinct, basenames shown | **identical**, no basename |
| 125 | distinct, basenames shown | **identical**, no basename |
| 150 | distinct, basenames shown | distinct, no basename |
| 250 | distinct, basenames shown | distinct, basenames shown |

The realistic case needs ~150 px to become distinguishable and ~250 px to show the
filename. The committed fixture hides that entirely.

**Required:** restore the plan's fixture — two paths sharing a long directory
prefix and ending in `customers.parquet` and `loans.parquet` — and make the width
explicit rather than inheriting whatever the default happens to be:

```python
header.resizeSection(1, 258)   # 250 px of paint budget after cell padding
```

Then assert, at that width: the two rendered strings differ; each contains its own
basename; and `view.textElideMode() == Qt.TextElideMode.ElideMiddle`.

Add one further assertion at the same width that pins the fix to its cause —
`ElideRight` at 258 px must produce two identical strings, `ElideMiddle` must not.
That is what makes the test fail if someone reverts the mode, independent of
fixture choice.

Do not assert anything about the *default* 100 px width in this test. At that width
the reported defect is genuinely not fixable by elision alone, which is R2's
subject.

### R2 — Task 2's specified resize modes do not fix the reported case at the user's actual dock width

This is a defect in the plan I wrote, surfaced by your fixture observation. Task 2
as specified gives `Alias`, `Format`, and `Schema status` `Interactive` mode, which
leaves them at Qt's 100 px default. Three fixed columns consume 300 px before the
stretched File column gets anything.

Measured by applying Task 2 exactly as the plan specifies, against the user's real
paths from `fix/Screenshot_20260802_132729.png`:

| dock width | File column | rows distinct? | basename visible? |
|---|---|---|---|
| 450 (the user's actual width) | 136 px | **no** | no |
| 600 | 286 px | yes | yes |
| 800 | 486 px | yes | yes |

At the width the user actually runs, Tasks 1 and 2 combined would leave both rows
rendering identically — the exact symptom being fixed. The same measurement with
`ResizeToContents` on the two narrow columns:

| dock width | File column | rows distinct? | basename visible? |
|---|---|---|---|
| 450 | 190 px | **yes** | partially (`…omers.parquet`) |
| 600 | 340 px | yes | yes |

`Format` holds `parquet` / `csv` and `Schema status` holds `Ready` / `Loading`;
neither needs 100 px, and neither benefits from being user-resizable.

**Required — amend Task 2 when you reach it:**

- File (logical index 1): `QHeaderView.ResizeMode.Stretch`, as already planned;
- Format (2) and Schema status (3): `QHeaderView.ResizeMode.ResizeToContents`,
  **not** `Interactive`;
- Alias (0): `Interactive`, since aliases are user-supplied and vary in length;
- keep `setSectionsMovable(True)`.

Task 2's test must add the user-facing acceptance criterion, not just the
`wide > narrow` growth check already in the plan: at a **450 px** dock width, with
the real `customers.parquet` / `loans.parquet` fixture, the two File cells must
render as different strings. Under the `Interactive` variant that assertion fails
at 136 px, so it is a live test of this decision.

Record in the session log that full-basename visibility at 450 px is **not**
achievable — 190 px cannot hold a 54-character path — and that the accepted
outcome at that width is row distinguishability, with full readability from roughly
600 px. Do not chase the stronger property.

## Not blocking — for the human, no action from you

`/tmp/wherewolf-cache-recovery-20260810-1543` holds 911 MB on the quota-limited
tmpfs, left by this round's environment recovery. Preserving rather than deleting
it was the right call. Cleanup is the human's decision; do not remove it.

## Scope reminder

R1 and R2 are the only changes requested. R2 is instruction for when you reach
Task 2 — do not implement Task 2 in this round. Fix R1, re-run the gates, commit,
re-mark the round, and stop.

STATUS: CHANGES_REQUESTED
