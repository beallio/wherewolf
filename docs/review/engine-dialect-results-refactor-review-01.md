# Review — engine-dialect-results-refactor (round 01)

Branch: `feat/engine-dialect-results-refactor`
Commit reviewed: `dd70f20` (HEAD; impl commits `bf8ceca`, `4bef6d2`, `338e69d`)
Reviewed against: `docs/plans/2026-06-24_engine-dialect-results-refactor.md`

## Verdict

APPROVED. All three planned phases are implemented exactly as specified, with correct
caching/import semantics and full behavior parity. No changes required.

## Gate status

Re-run independently by the orchestrator:

- `ruff check src/` — All checks passed.
- `ruff format` — clean.
- `ty check src/` — All checks passed.
- `pytest` — 61 passed, 1 skipped.
- Working tree clean; review notes not deleted.

## Findings (all satisfied)

**Phase 1 — dialect mapping (#4)**
- `DIALECT_MAPPING` added to `src/wherewolf/constants.py`; both inline dicts (`app.py:438`, `:522`)
  removed and replaced with the constant (now `app.py:399-400` and `ui/results.py:48,56`).
- `tests/test_constants.py` extended with `test_dialect_mapping`; existing
  `test_supported_extensions` (`len == 5`) left untouched as required.

**Phase 2 — engine factory (#3)**
- New `src/wherewolf/engines.py` holds the `@st.cache_resource` getters and `get_engine`, which
  routes through the cached getters (singletons preserved — no fresh instantiation; the
  `DuckDBEngine._registered_views` idempotency cache is retained). Unknown names raise `ValueError`.
- All three `if engine_name == "DuckDB"` blocks eliminated (verified by grep): schema
  (`app.py:282`), run (`app.py:396`), full-export (`ui/results.py:116`).
- `execution` package remains Streamlit-free.
- Getters re-imported into `app.py`'s namespace (`# noqa: F401`) so existing `AppTest` patch paths
  resolve; `tests/test_app_cancel.py` patch target correctly updated to `wherewolf.engines.DuckDBEngine`.
- `tests/test_engines.py` added (duckdb/spark/unknown).

**Phase 3 — results extraction (#2)**
- `src/wherewolf/ui/results.py` adds `ResultsView.render(result, translator, get_engine)`; export
  helpers `encode_export`/`export_base_name` moved out of `app.py`; exported via `ui/__init__.py`.
- No circular import: `results.py` imports only `constants`/`execution`/`export`/`translation`
  (verified by grep); `get_engine` is injected as a parameter.
- `app.py` block replaced with the planned 4-line call; file reduced 647 → 481 lines.
- `tests/test_results.py` covers success and failure rendering.

## Behavior parity

Engine/dialect dedup confirmed complete; translation HUD, metrics/preview, export, and full-export
re-run paths moved verbatim. Manual UI smoke testing remains deferred (opt-in) per the plan.

## Prior findings

None — this is the first review round; nothing outstanding.

## Finalization instructions

Proceed to finalize: confirm review notes committed, confirm clean tree, then run
`scripts/orchestration/finalize engine-dialect-results-refactor`. Finalize merges
`feat/engine-dialect-results-refactor` into `main` locally; push and release remain opt-in
(`ORCH_PUSH=1`). Leave both markers in place after finalization.

STATUS: APPROVED
