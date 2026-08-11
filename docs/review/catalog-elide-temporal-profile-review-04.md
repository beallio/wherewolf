# Review — catalog-elide-temporal-profile (round 04)

Branch: `feat/catalog-elide-temporal-profile`
Reviewed against: `docs/plans/2026-08-10_catalog-elide-temporal-profile.md`
Round contents: `5a2fbed` — R3 from review 03.

## Verdict

**Task 2 accepted — proceed to Task 3.**

Defect A is now fully implemented and every guard around it is proven live.

## Gate status

Re-run independently on `5a2fbed`:

```text
./run.sh uv run pytest -q     497 passed, 7 deselected in 13.17s
./run.sh uv run ty check src/ All checks passed!
git status --porcelain        (empty)
```

Orchestrator mutation check — columns 2 and 3 reverted to `Interactive`:

```text
E  AssertionError: File cells are indistinguishable at 450 px:
   '/run/medi…s.parquet', '/run/medi…s.parquet'; available_width=128
1 failed, 15 deselected in 0.63s
```

Mutation reverted, tree confirmed clean. The test now fails for exactly the right
reason and prints the two identical strings and the paint budget. Together with the
round-02 `ElideMiddle` mutation, both halves of Defect A are guarded by tests that
have been shown to fail.

## Task 3 — build to the plan as written

No amendments. `docs/plans/2026-08-10_catalog-elide-temporal-profile.md` §"Task 3 —
Carry profile statistics as text" is accurate; work from it directly. The points
most likely to be got wrong:

- **Do not touch `src/wherewolf/execution/registry.py` in this round.** `_as_float`
  stays on all five statistic fields and still crashes on temporal columns after
  this task. Task 4 fixes that. The separation is the point: this round proves the
  type widening is behaviour-preserving for numeric columns on its own.
- Widen `avg`, `std`, `q25`, `q50`, `q75` on `ColumnProfile` to `str | None`.
  Leave `min`, `max`, `approx_unique`, `count`, `null_percentage` alone.
- Drop the now-redundant `str()` at `schema_panel.py:312`, keeping the
  `is not None` guard.
- Update the existing `ColumnProfile(...)` constructions listed under "Blast
  radius" in the plan's Context to pass strings.
- **`avg=1.5` becoming `avg="1.5"` must still render the cell text `1.5`.** If an
  existing assertion about rendered output has to change, stop and say so in the
  session log rather than editing the expectation — that would be a signal
  something broke.

Red evidence for this round is either a test failure or a `ty` error, depending on
which you hit first. Record whichever it is verbatim, then record the passing
`./run.sh uv run ty check src/` output after the widening.

## Scope

Task 3 only. Do not begin Task 4. Gates, commit, re-mark, stop.

STATUS: CHANGES_REQUESTED
