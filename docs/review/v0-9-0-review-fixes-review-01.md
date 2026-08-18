# Review — v0-9-0-review-fixes (round 01)

Branch: `feat/v0-9-0-review-fixes`
Reviewed against: `docs/plans/2026-08-18_v0-9-0-review-fixes.md`

## Verdict

Changes are required. The automated gate is green, and the parameterized-export,
lexical-token, document-baseline, and saved-query-cache changes are directionally
sound. However, the result-provenance implementation introduces a reproducible
cross-tab result leak, catalog persistence failures are not actually visible to
the user after an add, and several explicitly required Red-Green regression
paths were skipped. This round does not yet satisfy the plan or the repository's
strict TDD/cache-isolation contract.

## Gate status

- Round-complete marker: valid at `7a9b128579e06a0facc37c510feee58e6e86b434`.
- Tracked worktree: clean before review; no review notes deleted.
- Independent `scripts/orchestration/run-quality-gates`: passed.
  - Ruff check: passed.
  - Ruff format: 175 files unchanged.
  - `ty check src/`: passed.
  - pytest: `620 passed, 7 deselected`.
- Implementer-recorded mutation controls: the missing DuckDB parameter forwarding
  and startup-editor capture mutations both made their focused tests fail, then
  passed after reversal.
- Independent result-provenance probe: failed. A direct saved query started from
  tab 1, completed after switching to tab 2, rendered into tab 2; switching back
  to tab 1 cleared it, and neither `_EditorTabState` retained the result.
- Independent persistence probe: failed. A fail-once `CatalogStore.save()` left
  the store empty and `_last_persisted_catalog` unchanged, but the visible status
  immediately became `Added `data` to catalog.` rather than the save error. The
  close retry subsequently persisted the entry, confirming that retry state was
  retained but the warning was lost.
- Cache-isolation check: failed. `src/wherewolf/__pycache__/` remains in the
  repository, including a `_build_info` bytecode file generated during this
  round's gate window.

## Required changes

1. **P1 — Preserve the origin editor and provenance for direct saved-query
   results.** `MainWindow._execute_sql()` currently stores `None` as the origin
   for a direct saved query, and `_on_query_result_ready()` consequently renders
   the completion into whichever tab is active at completion. It also stores the
   result in no tab, so it disappears on the next tab switch. Implement the
   plan's explicit provenance model instead of using `None` as both provenance
   and ownership: retain the launch editor as display owner, separately mark the
   request/result as `editor` versus `saved-query`, store the request/result and
   provenance in that editor's `_EditorTabState`, render only when that editor is
   active, retain history if the owner closes, and reject Apply Query Order when
   the stored provenance is not editor-owned. Add a failing regression that
   launches a saved query in tab 1, switches to tab 2 before completion, proves
   tab 2 is not overwritten, switches back to tab 1 and sees the result, then
   proves ordering leaves tab 1 SQL unchanged with the explanatory status.

2. **P1 — Make catalog persistence failure reporting survive the success path.**
   Catching `OSError` keeps later listeners alive, but `_handle_add_result()`
   immediately overwrites `Could not save dataset catalog` with `Added ...`.
   Surface the unsaved-catalog condition through a durable UI channel or retained
   error state that an ordinary success message cannot erase. Preserve the
   current fail-closed projection behavior and close retry. Add the plan-required
   fail-once window test proving, in order: service and catalog model update,
   persisted storage remains old, the unsaved warning remains visible after the
   add result is handled, `_last_persisted_catalog` does not advance, and a later
   mutation or close retry writes the complete latest projection. This production
   behavior was added without a preceding failing window test in round 1, so the
   correction must restore Red-Green evidence.

3. **P1 — Complete the catalog refresh contract with window-level tests.** Add
   failing tests that exercise `_on_refresh_catalog_schema()` rather than only
   `CatalogService.refresh_availability()`: a returned file must clear
   `unavailable` and queue schema plus eligible profile work; a file that has
   disappeared must become unavailable and queue neither worker. Also test the
   public service's documented `KeyError` for an unknown ID. Keep listener
   notification assertions for both availability directions.

4. **P2 — Complete the plan-mandated editor/document regression matrix.** The
   round added only Toggle Comment plus Replace All cross-tab coverage and only
   one non-pristine Open SQL case. Add focused failing tests for:
   - cross-tab Undo and Redo;
   - Find Next and Replace Next after the non-modal dialog is retargeted;
   - accepted theme persistence across every existing editor and a subsequently
     created tab (the rejection path is already covered);
   - Open SQL from a clean file-backed tab opening beside it;
   - Open SQL cancellation/read or UTF-8 failure leaving the tab count and
     current buffer untouched;
   - restored missing/unreadable file-backed drafts using the unknown baseline
     and remaining visibly modified;
   - dirty-state recomputation when switching between clean and dirty
     file-backed tabs.

   These cases are direct requirements in plan tasks 4 and 5; do not substitute
   structural assertions or `.trigger()` coverage for the missing state
   transitions.

5. **P2 — Close the verification and cache-isolation gaps.** Remove repository-
   local generated cache directories, including `src/wherewolf/__pycache__/`,
   after the final gates and verify no `__pycache__`, `.pytest_cache`,
   `.ruff_cache`, or `.venv` directories remain under the repository. Fulfil the
   plan's desktop smoke obligations with reproducible offscreen Qt probes/tests
   where an interactive display is unavailable; defer only the explicitly
   documented Windows-native behavior. Update the session JSON with the new Red
   failures, Green results, independent/full gate tally, smoke evidence, cache
   check, files/tests added, and remaining platform deferrals.

STATUS: CHANGES_REQUESTED
