# Review — count-all-rows (round 01)

Branch: `feat/count-all-rows`
Reviewed against: `docs/plans/2026-08-22_count-all-rows.md`

## Verdict

The isolated controller and DuckDB count path are well structured, and the
current suite is green. One user-visible lifecycle defect prevents approval:
row-count state from an earlier request survives when a later ordinary query
becomes the tab's current result. This can disable a valid Count All action and
show a stale success, failure, or cancellation message for data that has never
been counted.

## Gate status

- Independent `./run.sh scripts/orchestration/run-quality-gates`: passed.
- Ruff check and format verification: passed.
- `ty check src/`: passed.
- Pytest: 757 passed, 7 deselected.
- Manual regression reproduction: failed as described below.

## Required changes

1. Reset `row_count_request_id`, `row_count_status`, and
   `row_count_message` whenever a new ordinary query/result supersedes the
   tab's prior request, even when the row-count controller is no longer
   counting. The current `_invalidate_active_row_count()` returns immediately
   when `counting` is false, and `_on_query_result_ready()` then installs the
   new request without clearing the old count state. A completed count followed
   by a new truncated request reproduced this state:

   ```text
   status=complete total_rows=None button_enabled=False message="All rows counted."
   ```

   Add a regression that completes a count for request 1, delivers a new
   truncated request 2, and proves request 2 is idle, has no total, enables
   Count All, and shows no stale message. Cover the same reset after failed and
   cancelled terminal states, and prove a delayed completion for request 1
   cannot change request 2.

2. Complete the plan-required MainWindow lifecycle matrix. Add focused tests
   proving failure and cancellation preserve the preview and render inline
   state; completion for a closed origin tab is ignored; a background-tab
   completion is retained and restored when revisiting that tab; and counting
   preserves filter, local sort, selection, history, Messages, preview export,
   and full-result export state. Add an explicit cancellation-priority test for
   the coexistence of query, export, and count work. Fix any behavior those
   tests expose.

3. Run the plan's failure matrix and a valid count immediately after each
   failure/cancellation case to prove the controller remains reusable. Record
   the exact commands and resulting tallies in the feature's session log, then
   rerun the full quality gates.

STATUS: CHANGES_REQUESTED
