# Review — result-pagination (round 01)

Branch: `feat/result-pagination`
Reviewed against: `docs/plans/2026-08-22_result-pagination.md`

## Verdict

The isolated SQL, adapter, controller, and per-tab routing are generally sound,
and the full suite is green. One user-visible Count All coexistence defect
prevents approval: when a known total says more rows exist but the next-page
probe is empty, the UI reports that no further rows exist while leaving Next
enabled from the stale total.

## Gate status

- Independent `./run.sh scripts/orchestration/run-quality-gates`: passed.
- Ruff check and format verification: passed.
- `ty check src/`: passed.
- Pytest: 821 passed, 7 deselected.
- Original plan SHA-256: matched.
- Direct known-total/empty-probe reproduction: failed as described below.

## Required changes

1. Make the page probe's exhaustion an authoritative upper bound even when
   `QueryResult.total_row_count` is populated. `_on_page_result_ready()`
   currently sets `page_has_next = False` for an empty next page, but
   `_has_next_page()` ignores it whenever a total is known. The direct
   reproduction produced this contradictory state:

   ```text
   next_enabled=True page=Page 1 status=rows 1-2 of 5 · Page 1 · The next page was empty; no further rows are available.
   ```

   Add a regression with a known total of five, page size two, and an empty
   page-2 probe. It must retain page 1 and its frame, display the explanation,
   and disable Next. Also cover a non-empty result whose `has_next=False`
   disagrees with a larger known total; the actual probe must prevent repeated
   navigation into nonexistent rows. Retain the known total for range display.

2. Add the coexistence proof required because Count All Rows was already on
   `dev` when this plan started. Show that pagination neither invokes nor
   requires the row-count controller, preserves a total delivered by row
   counting across page changes, and keeps the full cancellation order
   `export -> query -> page -> row count`. Assert window shutdown reaches both
   auxiliary controllers. Fix any behavior those tests expose.

3. Correct the session log: Count All integration is present and cannot be
   listed as a future/deferred interaction. Record the new coexistence and
   contradictory-total tests, the direct regression result, focused tallies,
   and the final quality-gate tally. Rerun the plan's focused suites and full
   gates before recreating the round-complete marker.

STATUS: CHANGES_REQUESTED
