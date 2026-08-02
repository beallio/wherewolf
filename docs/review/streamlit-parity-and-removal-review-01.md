# Review — streamlit-parity-and-removal (round 01)

Branch: `feat/streamlit-parity-and-removal` @ `5cd45f1`
Reviewed against: `docs/plans/2026-08-01_streamlit-parity-and-removal.md`

## Verdict

CHANGES_REQUESTED — **the parity gate did not hold.** Roughly half of the audit's positive
claims do not survive checking, and Streamlit was deleted on the strength of them.

The mechanics of this round are the best of the migration. The audit's *content* is the problem,
and it is the one thing in this phase that had to be right.

## What you did well — genuinely

- **Eleven commits, one per task, deletions separated by target.** This was a stated requirement
  after slipping in two consecutive phases, and you met it exactly. If a deletion turns out to
  have broken something, it is one `git bisect` away.
- **No Streamlit residue.** `grep -rn "streamlit\|streamlit_ace\|AppTest" src/ tests/ pyproject.toml .github/`
  returns nothing. `app.py`, `engines.py`, `ui/results.py`, `ui/file_browser.py` and
  `export/exporter.py` are gone. `.streamlit/` is an empty untracked husk — git does not remove
  empty directories, and nothing tracked remains. Not a defect.
- **Entry points are right.** `wherewolf` → `cli:main` → `desktop_main()`, `__main__.py` present,
  `wherewolf-desktop` preserved.
- **The audit's structure is correct** — 87 rows, with real `GAP` (4) and `MANUAL` (5) entries
  rather than blanket claims. Marking "no browser tab is started" as `MANUAL` instead of
  inventing a test for it is exactly right, and the `GAP` rows correctly pointed at Task 4.
- Gates pass: 345 passed, 7 deselected. Crash gate: **0 crashes / 25** so far, second batch
  running.

## Required changes

### J1. Thirty-one of sixty-two cited mappings do not hold

I spot-checked one row, found it wrong, and then had every cited row checked. Of **62 rows
citing a test node id, 31 do not genuinely assert their criterion** — my one plus thirty more.

**The clearest case, and why this matters:**

> *"active local sort is labelled 'Sorted preview only.'"* → cited: `test_local_sort_does_not_rerun_query`

That test asserts `executed_count == 0` — that sorting does not re-run the query. It says nothing
about a label. And:

```text
grep -rn "Sorted preview" src/ tests/  →  NOT PRESENT ANYWHERE
```

The feature does not exist. A Required criterion was recorded as satisfied for behaviour that
was never built. The user consequence is concrete: someone sorts a 1000-row preview of a
10-million-row table with nothing telling them they are looking at a sorted *page* — precisely
the confusion the local-sort/full-query-ordering split was designed to prevent in Phase 10.

**Two rows cite node ids that do not exist at all**, which shows the audit was never validated
by running it:

```text
pytest --collect-only | grep -c "test_importing_desktop_application_is_free_of_streamlit_and_pyspark
                                |test_catalog_dock_drag_drop_deduplicates_resolved_paths"  →  0
```

The remaining failures fall into three kinds, and they are not equally severe:

1. **Wrong property entirely** — e.g. *"Format SQL exists on toolbar, menu, context menu, and
   shortcut"* cites a test asserting the unrelated **Show Completion** action; *"dialect
   keywords/functions are suggested"* cites a metadata-retrieval test that never exercises
   completion. These are the serious ones.
2. **Partial coverage presented as full** — *"columns can be moved, resized, auto-sized, hidden,
   shown, and reset"* cites a test covering move/hide/reset only; *"Messages tab shows parse,
   translation, engine, and export errors"* cites a test covering one engine error;
   *"Schema tab shows real schema or a real error"* cites the error case only.
3. **Criterion narrower than claimed** — *"preview truncation is clearly indicated"* cites a test
   that sets `truncated=False` and never checks an indicator; *"Ctrl+C copies TSV"* cites a test
   calling `copy_selection()` directly rather than the shortcut.

The full list with file:line evidence is in the delegated report; work from that.

### What to do

**Do not revert the deletions.** The code is sound, the tests pass, the commits are clean, and
nothing is merged — this was caught before `dev`. Reverting would cost more than it buys.

1. **Redo the audit with each mapping opened and verified.** Half the positive claims failed, so
   spot-checking is not sufficient this time. For every row: open the cited test and confirm it
   asserts the criterion. If it asserts only part, mark it `PARTIAL` with what is missing.
2. **Close the real gaps.** Implement the "Sorted preview only" indicator, and add the missing
   assertions for partial rows.
3. **Fix the two phantom node ids** and add a check that every cited node actually collects —
   `pytest --collect-only` makes this mechanical, and it would have caught both.
4. Where a criterion genuinely cannot be automated, move it to `MANUAL` with a reason. `MANUAL`
   is an acceptable answer; a false citation is not.

## The process point, stated plainly

The plan said: *"A criterion mapped to a test that does not actually assert it is worse than a
`GAP`, because it converts an unknown into a false assurance."* That is exactly what happened,
across half the audit.

I do not think this was careless — the audit is long, the criteria are dense, and the structure
shows real effort. But an audit is only worth the verification behind it, and this one asserted
coverage it had not checked. The mechanical fix is the one this project has landed on repeatedly:
**after any claim you report, run the command that would fail if it were untrue.** For a parity
matrix, that means opening the test.

## Verification before marking complete

- The re-verified audit, with `PARTIAL` used where coverage is incomplete.
- Every cited node id confirmed to collect (`pytest --collect-only`).
- The "Sorted preview only" indicator implemented and asserted.
- V7 mutation 3: break a criterion the audit claims is covered; its cited test must FAIL. Do this
  for **three** rows across different subsections this time, not one.
- `./run.sh uv run pytest -q` on 3.14 and `--python 3.12`; restore with
  `./run.sh uv sync --all-extras --dev --python 3.14`.
- `./run.sh uv run pytest -q -m spark` — the Spark tier must still pass.
- **V5 accounting:** the tally went 364 → 345. State which 19 tests were removed and confirm each
  covered Streamlit-only behaviour.
- **V6 per-leg install check** — three dependencies were removed; state what each CI leg installs
  versus what its tooling needs. This is where the previous phase broke.
- `git status --short` → empty.

**Already measured by review — do not re-run:** the residue check, entry-point routing, and the
crash gate (0/25, second batch in flight; I will report the final 50).

## Constraints

Do not revert the deletions. Do not delete a test merely because it mentions Streamlit. Do not
mark a criterion covered without opening the test you cite. Do not remove `timid = true`. Do not
touch `main`. Do not bump the package version — 0.6.0 belongs to Phase 15.

## Deferred

The `MANUAL` parity items remain unverified by a human and are a **release gate**, not a test
gate. List them prominently in the close-out so the maintainer knows what still needs clicking
before 0.6.0 ships.

STATUS: CHANGES_REQUESTED
