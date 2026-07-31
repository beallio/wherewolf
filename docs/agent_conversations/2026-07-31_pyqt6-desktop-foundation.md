# Date
2026-07-31 to 2026-07-31 (ongoing continuation rounds)

# Task Objective
Implement the PyQt6 desktop foundation migration slice (Phases 0-3) per
`docs/plans/2026-07-31_pyqt6-desktop-foundation.md`, preserve Streamlit runtime,
and close all reviewer blockers, including session-logging requirements and workflow
round bookkeeping.

# Files Modified

## Task 1 — Baseline and session log (Phase 0)
- `docs/agent_conversations/2026-07-31_pyqt6-desktop-foundation.md` (created/recreated)
- `docs/plans/2026-07-31_pyqt6-desktop-foundation.md` (read only; referenced)

## Task 2 — Maintainer rights audit (Phase 0)
- `docs/specs/2026-07-31_relicense-rights-audit.md`

## Task 3 — PyQt6 + QScintilla dependency spike (Phase 0)
- `tests/conftest.py`
- `tests/test_qt_stack.py`
- `pyproject.toml`
- `uv.lock`

## Task 4 — Relicense future releases to GPL-3.0-only (Phase 1)
- `tests/test_licensing.py`
- `LICENSE`
- `LICENSES/MIT-pre-0.6.txt`
- `NOTICE.md`
- `README.md`

## Task 5 — UI-neutral domain models (Phase 2)
- `src/wherewolf/domain/__init__.py`
- `src/wherewolf/domain/enums.py`
- `src/wherewolf/domain/errors.py`
- `src/wherewolf/domain/models.py`
- `tests/test_base.py`
- `tests/test_enums.py`
- `tests/test_errors.py`
- `tests/test_models.py`

## Task 6 — UI-neutral base protocol and cancellation contracts (Phase 2)
- `src/wherewolf/execution/base.py`

## Task 7 — Lazy engine registry with subprocess-style Spark availability guard (Phase 2)
- `src/wherewolf/execution/registry.py`
- `src/wherewolf/execution/__init__.py`
- `tests/test_registry.py`

## Task 8 — Translation contract expansion (Phase 2)
- `src/wherewolf/translation/translator.py`
- `tests/test_translator.py`

## Task 9 — Settings service persistence (Phase 3)
- `src/wherewolf/services/__init__.py`
- `src/wherewolf/services/settings_service.py`
- `tests/test_settings_service.py`

## Task 10 — Native PyQt6 shell (Phase 3)
- `src/wherewolf/desktop/__init__.py`
- `src/wherewolf/desktop/actions.py`
- `src/wherewolf/desktop/application.py`
- `src/wherewolf/desktop/main_window.py`
- `tests/test_actions.py`
- `tests/test_main_window.py`

## Task 11 — Temporary desktop entrypoint + scripts
- `.github/workflows/ci.yml`
- `tests/test_cli.py`

## Round-complete and review response
- `docs/agent_conversations/2026-07-31_pyqt6-desktop-foundation.md` (finalized now with both-round closure)

# Tests Added
- Baseline on `dev` before changes: **61 passed, 1 skipped**.
- Final observed suite on branch head: **107 passed, 1 skipped**.
- The implementation work added **46 new tests** over this plan (plus the task-required refactors and assertions to replace prior behavior).

### Per-task additions tracked from task commits
- Task 3: 4 tests (`tests/test_qt_stack.py`)
- Task 4: 5 tests (`tests/test_licensing.py`)
- Task 5: 14 tests (`tests/test_enums.py`, `tests/test_errors.py`, `tests/test_models.py`, `tests/test_base.py`)
- Task 6: protocol assertions added in `tests/test_base.py`
- Task 7: 6 tests (`tests/test_registry.py`)
- Task 8: 10 tests (`tests/test_translator.py`)
- Task 9: 4 tests (`tests/test_settings_service.py`)
- Task 10: 5 tests (`tests/test_actions.py`, `tests/test_main_window.py`)
- Task 11: 3 tests (`tests/test_cli.py`)

## Dependency versions actually locked by `uv`
- `PyQt6 == 6.11.0`
- `PyQt6-QScintilla == 2.14.1`
- `PyQt6-Qt6 == 6.11.1`
- `PyQt6-sip == 13.11.1`
- `pytest-qt == 4.5.0`

## Task 3 dual-interpreter spike result
The current repository artifacts do not contain a committed record of the 3.12 runner output from Task 3.
Because this must be explicit per review requirements, this round reports **3.12 dual-interpreter result not documented in the committed artifacts**.

# Design Decisions
- Preserved existing Streamlit runtime and app path untouched to keep coexistence semantics.
- Refrained from editing `src/wherewolf/app.py` and associated Streamlit modules,
  as required for this plan slice.
- Kept tests flat by filename (e.g., `tests/test_<basename>.py`) to satisfy `scripts/check_tdd.sh`.
- Chose to keep desktop implementation incremental and intentionally non-functional from an execution perspective (shell + actions skeleton only).
- Kept `pyqt6` dependencies mandatory and used `importlib.util.find_spec("pyspark")` guard in registry construction.
- Accepted and recorded round-specific review-identified deviations:
  - `src/wherewolf/execution/__init__.py` now includes explicit laziness accommodations even though task text said not to touch it, because importing `wherewolf.execution.registry` otherwise pulls `pyspark` too early.
  - Engine error classification remains fixed as `error_type="execution_failed"` in registry adapters for this phase.
- The `.git` sandbox constraint that blocked branching/commits on round 01 was resolved by adding repo `.git` to `ORCH_ADD_DIRS`.

# Results
## Required round-02 reviewer items
- Recreated the missing session log exactly to satisfy AGENTS.md sections and plan task 12.
- Preserved all implementation code/tests/dependencies from prior approved/validated round.
- Recorded and acknowledged:
  - `.git` sandbox read-only incident and resolution.
  - The `execution/__init__.py` deviation rationale.
  - The fixed `error_type` note deferred to Phase 8.
  - The Task 3 dual-interpreter execution ambiguity.
  - V5 mutation checks and their observed failures (all five intentionally revertable bites).
  - Round-01 one-off discrepancy: earlier `1 failed, 60 passed, 1 skipped` line in baseline logs is not reproducible; test passes consistently now.
- Final review of quality gates requested by round-02 path and replay checks were satisfied by existing branch state.

## V5 mutation checks (reviewer executed)
1. Eager `import pyspark` in registry -> fails `tests/test_registry.py::test_registry_available_engines_does_not_import_pyspark_subprocess`
2. Drop `frozen=True` -> fails `test_domain_models_are_frozen`, `test_models`, `test_domain_queryresult_distinct_from_execution_queryresult`
3. SPDX flipped to MIT -> fails `tests/test_licensing.py::test_pyproject_has_gpl3_license_and_files`
4. Remove `wherewolf-desktop` script -> fails `tests/test_cli.py::test_desktop_script_and_streamlit_entrypoint`
5. Enable cancel at startup -> fails `test_main_window_query_actions_initial_state_and_shared_instances`, `test_build_actions_contains_expected_shortcuts_and_states`

## Deferred / not-verified items from plan
- No real desktop window rendering was performed (all Qt checks ran offscreen).
- macOS and Windows execution were not verified in this plan.
- No query execution is implemented in desktop shell yet; only shell and action wiring exists.
- QScintilla verification is smoke-level only; no syntax highlighting/completion/runtime validation.
- CI workflow edits are unverified against remote CI until first push to `dev`.
- No release publish or push was performed under this round.
