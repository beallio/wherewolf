# Review — error-position-navigation (round 01)

Branch: `feat/error-position-navigation`
Reviewed against: `docs/plans/2026-08-22_error-position-navigation.md`

## Verdict

The core flow is well-scoped and the full quality gates pass, but the position mapping is not yet
safe for every editor snapshot. One reproducible UTF-8 offset mismatch can move the caret to the
wrong character, which violates the plan's fail-closed requirement. The planned negative-path and
activation coverage is also incomplete, so the currently untested guards need durable tests before
integration.

## Gate status

- `scripts/orchestration/run-quality-gates`: PASS (`678 passed, 7 deselected`; ruff check, ruff
  format check, `ty`, TDD enforcement, and review-note deletion check all passed).
- Branch/worktree before this review note: clean at `be2b36e` with a valid round-complete marker.
- Manual desktop behavior remains explicitly unverified, as recorded in the session log.

## Required changes

1. Fix the Scintilla-byte-offset/Python-codepoint mismatch in selected-fragment mapping. The
   `start` returned by `SqlEditor.text_to_run()` is an absolute Scintilla UTF-8 byte position, but
   `_navigation_target_for_result()` uses it as a Python string index. This can pass the exact
   fragment comparison and jump to the wrong repeated character when non-ASCII text occurs on an
   earlier line. A read-only reproduction with document `é\nAAAAA`, selection `AAAA` from line 2,
   and a DuckDB caret at column 1 produced `text_to_run() == ('AAAA', 3, 7)` and moved the cursor to
   `(1, 1)` instead of `(1, 0)`. Convert the stored start to a proven Python codepoint offset (or
   otherwise fail closed before constructing a target), and add a regression proving this exact
   case either lands on the first `A` or declines navigation, never the second `A`.
2. Add the negative-path tests required by the plan for translated SQL, bound parameters,
   multi-statement execution, direct saved-query execution, Spark, tab-expanded/error excerpts,
   Unicode column ambiguity, and a closed originating tab. Each case must assert that activation
   does not change the current tab or cursor. Also exercise real keyboard and mouse activation of
   the `QListWidget`; directly emitting `itemActivated` does not prove those input paths.
3. Run the complete required negative-control subset after the happy paths and record the exact
   commands, exit codes, and tallies in
   `docs/agent_conversations/2026-08-22_error-position-navigation.json`. Add the observed RED
   evidence for the implementation slices if it is available from this session; do not invent
   evidence if it was not retained, and explicitly record any missing evidence instead.

STATUS: CHANGES_REQUESTED
