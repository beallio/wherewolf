# Review — count-all-rows (round 02)

Branch: `feat/count-all-rows`
Reviewed against: `docs/plans/2026-08-22_count-all-rows.md`

## Verdict

The round-01 behavioral defect is fixed and its new lifecycle coverage passes.
The implementation is not yet ready to merge because required change 3 from
round 01 was only partially completed: the recorded command does not prove that
one controller returns to service after a terminal failure, and it omits
several cases from the plan's named failure matrix.

## Gate status

- Independent focused controller/UI/engine suites: 227 passed.
- Independent full quality gates: 768 passed, 7 deselected.
- Original plan SHA-256: matched.
- Review notes committed check: passed.

## Required changes

1. Add a focused `RowCountController` regression that uses the same controller
   instance for a failed submission and, after that worker has fully finished,
   a subsequent successful submission. Prove both terminal results carry their
   own request UUID, both adapters close exactly once, and the controller is not
   left counting or otherwise wedged. Include cancellation-to-success reuse on
   the same controller if it is not already proven by the same test structure.

2. Complete and accurately record the plan's negative-control matrix. The
   session log currently records multi-statement, source-change, cancellation,
   and worker-failure nodes followed by success nodes, but does not record the
   Spark, missing-source, superseded-request, or closed-tab cases named by the
   plan. Run all named cases, then run a valid truncated DuckDB count and its
   exact-summary assertion. Record the exact command and actual pytest tally;
   do not describe separate fresh-controller tests as same-controller reuse.

3. Rerun the focused suites and full quality gates, commit the test/session-log
   correction, and recreate the round-complete marker.

STATUS: CHANGES_REQUESTED
