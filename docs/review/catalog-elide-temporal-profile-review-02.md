# Review — catalog-elide-temporal-profile (round 02)

Branch: `feat/catalog-elide-temporal-profile`
Reviewed against: `docs/plans/2026-08-10_catalog-elide-temporal-profile.md`
Round contents: `6fd183f` — R1 from review 01.

## Verdict

**Task 1 accepted — proceed to Task 2.**

R1 is fully addressed. The fixture is back to `customers.parquet` /
`loans.parquet`, the width is pinned explicitly at 258 px instead of inherited,
and the `ElideRight` control assertion I asked for is present and correct.

## Gate status

Re-run independently on `6fd183f`:

```text
./run.sh uv run pytest -q     495 passed, 7 deselected in 13.09s
./run.sh uv run ty check src/ All checks passed!
git status --porcelain        (empty)
```

Mutation check performed by the orchestrator — `ElideMiddle` reverted to
`ElideRight` in `catalog_dock.py`, then the targeted test re-run:

```text
>       assert first_middle != second_middle, (
E       assert '/very/long/shared/prefix/directory/segme…' != '/very/long/shared/prefix/directory/segme…'
1 failed, 13 deselected in 0.61s
```

The mutation was reverted and the tree confirmed clean. The test is live: it fails
for the right reason, with the two identical strings printed. Task 1 is proven, not
merely green.

## Task 2 — build to this amended specification

R2 from review 01 stands unchanged and is restated here so this note is
self-contained. **The plan's own Task 2 text is superseded on the resize modes.**

On the catalog view's horizontal header:

- File (logical index 1): `QHeaderView.ResizeMode.Stretch`;
- Format (2) and Schema status (3): `QHeaderView.ResizeMode.ResizeToContents`
  — **not** `Interactive`, which is what the plan text says;
- Alias (0): `QHeaderView.ResizeMode.Interactive`;
- keep the existing `setSectionsMovable(True)`.

The reason, measured against the user's real paths from
`fix/Screenshot_20260802_132729.png`: with `Interactive` on the three non-File
columns they hold Qt's 100 px default, consuming 300 px, and a 450 px dock — the
user's actual width — leaves the File column 136 px, at which both rows still
render identically. With `ResizeToContents` on columns 2 and 3 the File column gets
190 px and the rows become distinguishable.

Tests for this task, both required:

1. the growth check already in the plan — File section size at a 900 px dock is
   strictly greater than at a 400 px dock, with both numbers in the failure
   message;
2. the user-facing criterion — at a **450 px** dock width, with the
   `customers.parquet` / `loans.parquet` fixture, the two File cells render as
   different strings. This one fails under the `Interactive` variant, so it is a
   live test of the decision above and not decoration.

Record in the session log that a full basename at 450 px is **not** achievable —
190 px cannot hold a 54-character path — and that the accepted outcome at that
width is row distinguishability, with full readability from roughly 600 px. Do not
chase the stronger property, and do not compensate by shortening the fixture.

## Scope

Task 2 only. Do not begin Task 3. Run the gates, commit, re-mark the round, stop.

STATUS: CHANGES_REQUESTED
