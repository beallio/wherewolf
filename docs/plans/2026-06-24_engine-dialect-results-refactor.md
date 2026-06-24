# Plan: Centralize Engine/Dialect Logic and Extract Results View (engine-dialect-results-refactor)

## Context

`src/wherewolf/app.py` is a 647-line Streamlit script that mixes configuration, session-state
init, helpers, sidebar, editor, execution orchestration, and results rendering. A code-quality
review flagged three concrete, verified problems; this plan addresses those three. It deliberately
**defers** larger, higher-risk items (typed `AppState` dataclass / controller layer) — do **not**
attempt those here.

Verified facts to rely on:

- The dialect map `{"DuckDB": "duckdb", "Spark": "spark", "Azure SQL": "tsql"}` is duplicated at
  `app.py:438` and `app.py:522`. (#4)
- Engine selection `if engine_name == "DuckDB": ... else: ...` is duplicated **three** times:
  `app.py:315-318`, `app.py:432-435`, `app.py:593-596`. (#3)
- The results-display block (`app.py:510-637`) is ~120 lines of tangled translation/metrics/
  preview/export logic at module top level. (#2)

Critical constraints — **honor these or you will introduce regressions**:

1. `get_duckdb_engine()` / `get_spark_engine()` are decorated with `@st.cache_resource`
   (`app.py:83-90`) and are **singletons across reruns**. `DuckDBEngine` keeps an in-memory
   connection plus a `_registered_views` idempotency cache (`duckdb_engine.py:12`). Any factory
   **must return these cached singletons**, never freshly-instantiated engines.
2. The `execution` package (`src/wherewolf/execution/`) is currently Streamlit-free and unit-
   testable. **Do not import `streamlit` into the `execution` package.** Put the Streamlit-aware
   caching layer in a new top-level module (see Task 2).
3. `Azure SQL` is a **translate-only** dialect, not an execution engine. The engine selectbox
   (`app.py:292`) intentionally lists only `["DuckDB", "Spark"]`. Do not add Azure SQL to it.
4. `Translator.VALID_DIALECTS = {"duckdb", "spark", "tsql"}` already exists
   (`translation/translator.py:7`). The new constant is the **UI-name → sqlglot-key** map only.
5. The app is tested via `streamlit.testing.v1.AppTest.from_file("src/wherewolf/app.py")`
   (see `tests/test_app.py`, `tests/test_app_flow.py`). Existing tests patch symbols on
   `wherewolf.app` (e.g. `patch("wherewolf.app.FileBrowser.render_explorer")`). Keep import names
   resolvable from `wherewolf.app`.

**Slug used throughout this plan:** `engine-dialect-results-refactor`

---

## Orchestration Contract

**Slug:** `engine-dialect-results-refactor`

**Plan file:**

```text
docs/plans/2026-06-24_engine-dialect-results-refactor.md
```

**Implementation branch:**

```text
feat/engine-dialect-results-refactor
```

**Round-complete marker:**

```text
/tmp/wherewolf/engine-dialect-results-refactor_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/engine-dialect-results-refactor_finalized
```

**Review notes:**

```text
docs/review/engine-dialect-results-refactor-review-*.md
```

Each review note ends with exactly one status trailer:

```text
STATUS: CHANGES_REQUESTED
```

or:

```text
STATUS: APPROVED
```

---

## Required Agent Protocol

1. Use the **implementer** skill.
2. Work from the repository root.
3. Branch from `main`.
4. Commit this plan as the first commit on the implementation branch.
5. Follow TDD where behavior changes are testable.
6. Run quality gates before marking any round complete.
7. Do not write your own review.
8. Do not create files under `docs/review/`.
9. Do not delete files under `docs/review/`.
10. Review notes are durable audit records and must be committed.
11. Resolving a review note means:
    - implement the requested changes;
    - run quality gates;
    - commit the code/docs changes;
    - commit the review note itself if it is not already committed;
    - recreate the round-complete marker.
12. After finalization, stop polling and exit cleanly.

---

## Setup

Start from `main`:

```bash
git checkout main
git pull --ff-only origin main
git checkout -b feat/engine-dialect-results-refactor
```

Commit this plan first:

```bash
git add docs/plans/2026-06-24_engine-dialect-results-refactor.md
git commit -m "docs(plan): add engine-dialect-results-refactor implementation plan"
```

---

## Implementation Tasks

Do the three phases below **in order**. Each phase is **one atomic commit** (Conventional
Commits). Run quality gates and ensure a clean tree before each commit. Do **not** commit the
unrelated untracked root files `code-quality-review-wherewolf.md` / `feature-ideation-wherewolf.md`.

### Phase 1 — Centralize the dialect mapping (#4)

**Goal:** one source of truth for the UI-name → sqlglot-dialect-key map.

**Files:** `src/wherewolf/constants.py`, `src/wherewolf/app.py`, `tests/test_constants.py`.

1. **(RED)** In `tests/test_constants.py`, add a test importing `DIALECT_MAPPING` from
   `wherewolf.constants` asserting:
   - `DIALECT_MAPPING == {"DuckDB": "duckdb", "Spark": "spark", "Azure SQL": "tsql"}`
   - every value is in `Translator.VALID_DIALECTS` (`from wherewolf.translation import Translator`).
   Run gates; confirm it fails (ImportError). ⚠️ Do **not** change the existing
   `test_supported_extensions` assertion `len(SUPPORTED_EXTENSIONS) == 5`.

2. **(GREEN)** In `constants.py` add:
   ```python
   # UI engine/dialect display name -> sqlglot dialect identifier
   DIALECT_MAPPING = {"DuckDB": "duckdb", "Spark": "spark", "Azure SQL": "tsql"}
   ```

3. In `app.py`:
   - Add `from wherewolf.constants import DIALECT_MAPPING` near the other imports.
   - Replace the local `dialect_mapping = {...}` at **`app.py:438`** with `DIALECT_MAPPING`
     (delete the literal; update the two lookups below it).
   - Replace the local `all_dialects_map = {...}` at **`app.py:522`** with `DIALECT_MAPPING`
     (update the `target_options` comprehension and the `target_dialect` lookup). *This line moves
     to `ui/results.py` in Phase 3; centralizing now still simplifies that move.*

4. Gates green, tree clean. **Commit:** `refactor(constants): centralize dialect mapping in DIALECT_MAPPING`

### Phase 2 — Engine factory, caching-preserving (#3)

**Goal:** remove the three duplicated `if engine == "DuckDB"` blocks behind a single factory,
**without** losing `@st.cache_resource` singletons and **without** importing Streamlit into the
`execution` package.

**Design decision (follow exactly):** create a new Streamlit-aware provider module
`src/wherewolf/engines.py`. Move the two cached getters out of `app.py` into it and add the
factory. Keeps `execution` pure and gives Phase 3 a clean, non-circular import.

**Files:** `src/wherewolf/engines.py` (new), `src/wherewolf/app.py`, `tests/test_engines.py` (new).

1. **(RED)** Create `tests/test_engines.py`:
   ```python
   import pytest
   from wherewolf.engines import get_engine
   from wherewolf.execution import DuckDBEngine, SparkEngine

   def test_get_engine_duckdb():
       assert isinstance(get_engine("DuckDB"), DuckDBEngine)

   def test_get_engine_spark():
       assert isinstance(get_engine("Spark"), SparkEngine)

   def test_get_engine_unknown_raises():
       with pytest.raises(ValueError):
           get_engine("Sqlite")
   ```
   Run gates; confirm failure. If calling `@st.cache_resource` getters outside a Streamlit run
   context raises (rather than warns) in this Streamlit version, keep `test_get_engine_unknown_raises`
   (it short-circuits before any getter call) and cover the positive paths via `AppTest` instead —
   but try the direct form first.

2. **(GREEN)** Create `src/wherewolf/engines.py`:
   ```python
   import streamlit as st
   from wherewolf.execution import DuckDBEngine, SparkEngine

   @st.cache_resource
   def get_duckdb_engine():
       return DuckDBEngine()

   @st.cache_resource
   def get_spark_engine():
       return SparkEngine()

   _ENGINE_GETTERS = {"DuckDB": get_duckdb_engine, "Spark": get_spark_engine}

   def get_engine(engine_name: str):
       """Return the cached singleton engine for a UI engine name."""
       if engine_name not in _ENGINE_GETTERS:
           raise ValueError(f"Unknown engine: {engine_name}")
       return _ENGINE_GETTERS[engine_name]()
   ```

3. In `app.py`:
   - Delete the two `@st.cache_resource` getter defs at `app.py:83-90`.
   - Add `from wherewolf.engines import get_engine, get_duckdb_engine, get_spark_engine`
     (re-import the getters so existing `AppTest` patch paths on `wherewolf.app` keep resolving).
   - Replace the schema branch at **`app.py:315-318`** with `temp_engine = get_engine(engine_name)`.
   - Replace the run branch at **`app.py:432-435`** with `engine = get_engine(engine_name)`.
   - Replace the full-export branch at **`app.py:593-596`** with
     `full_engine = get_engine(st.session_state.executed_engine_name)`.
     *(This block moves into `ui/results.py` in Phase 3 — make the substitution now so Phase 3 is a
     pure move.)*

4. Gates green (all existing `AppTest` tests still pass), tree clean.
   **Commit:** `refactor(engines): add get_engine factory and move cached engine getters`

### Phase 3 — Extract results rendering into `ui/results.py` (#2)

**Goal:** move the results-display block out of `app.py` into a cohesive UI component, matching the
existing `FileBrowser` convention (class with static methods, exported via `ui/__init__.py`).

**Files:** `src/wherewolf/ui/results.py` (new), `src/wherewolf/ui/__init__.py`,
`src/wherewolf/app.py`, `tests/test_ui_results.py` (new).

**What to move out of `app.py`:**
- Export helpers `encode_export` (`app.py:187-197`) and `export_base_name` (`app.py:200-208`).
  Confirm they are used **only** inside the results block first (they are: `encode_export` at 577 &
  607; `export_base_name` at 574). Move them into `ui/results.py`.
- The full rendering block `app.py:510-637`, i.e. both the `if result.success:` body **and** the
  `else:` error branch.

**Component shape (match `FileBrowser` style):**
```python
# src/wherewolf/ui/results.py
import streamlit as st
from wherewolf.constants import DIALECT_MAPPING
from wherewolf.execution import QueryResult
from wherewolf.export import Exporter
from wherewolf.translation import Translator

class ResultsView:
    @staticmethod
    def render(result: QueryResult, translator: Translator, get_engine) -> None:
        """Render translation, metrics, preview, and export UI for a query result."""
        # success branch (translation HUD, metrics, preview, export, full-export)
        # else branch: st.error("Query Failed") + details expander
```
- `get_engine` is passed in as a callable (the Phase-2 factory) to avoid a circular import between
  `ui` and `engines`/`app`. Use it for the full-export re-run (former `app.py:593-596`).
- The component reads/writes `st.session_state` directly (`executed_query`,
  `executed_input_dialect_key`, `executed_engine_name`, `executed_engine_query`, `catalog`,
  `full_export`) exactly as the original block did. Preserve every key name and semantic.
- Replace the former local `all_dialects_map` with imported `DIALECT_MAPPING`.

**Rewrite in `app.py`** — the block at `app.py:510-640` becomes:
```python
if st.session_state.query_result:
    ResultsView.render(st.session_state.query_result, translator, get_engine)
elif not st.session_state.catalog:
    st.info("👈 Please add a dataset to the catalog in the sidebar to begin.")
```
Add `from wherewolf.ui import ResultsView` (extend the existing `from wherewolf.ui import FileBrowser`).
Remove the now-unused `Exporter` import from `app.py` **only if** nothing else there uses it (grep first).

**Steps:**

1. **(RED)** Create `tests/test_ui_results.py` using `AppTest` end-to-end (the project's
   established pattern — avoid brittle mocking). Suggested cases:
   - Add `tests/test_data.csv` to the catalog (follow the `render_explorer` patching pattern in
     `tests/test_app.py` / `tests/test_app_flow.py`), set a query, click **Run**, let the
     background future complete, rerun, then assert `at.session_state.query_result.success is True`,
     a "Preview" element is present, and no `at.exception`.
   - A failure case (invalid SQL) asserting the `"Query Failed"` error path renders.
   See `tests/test_app_flow.py` for the run/wait-for-future/rerun pattern. Confirm red first (e.g.
   against a stub `ResultsView` that raises `NotImplementedError`).

2. **(GREEN)** Create `ui/results.py`; move helpers + rendering verbatim (adjusting only: import
   `DIALECT_MAPPING`, accept `translator`/`get_engine` params, use `st.session_state` directly).
   Export from `ui/__init__.py`:
   ```python
   from .file_browser import FileBrowser
   from .results import ResultsView
   __all__ = ["FileBrowser", "ResultsView"]
   ```
   Replace the block in `app.py` as shown above.

3. **(REFACTOR)** Remove dead imports in `app.py` (`ruff check` flags unused). Keep the `translator`
   instance in `app.py` (still used by the run-handler translation at `app.py:446-450`) and pass it
   into `ResultsView.render`.

4. **(VALIDATE)** Gates green. Verify **all** pre-existing `AppTest` tests still pass
   (`test_app.py`, `test_app_flow.py`, `test_app_cancel.py`, `test_ui_branding.py`,
   `test_file_browser_errors.py`) — they load the same `app.py`. Tree clean.

5. **Commit:** `refactor(ui): extract results rendering into ResultsView`

### DOCUMENT (after Phase 3, before finalize)

Write a session log at `docs/agent_conversations/2026-06-24_engine-dialect-results-refactor.md`
(or `.json` matching existing format) with: date, task objective, files modified, tests added,
design decisions (esp. the `engines.py` choice and why caching was preserved), and gate results.
Commit: `docs(session): log engine/dialect/results refactor`.

### Known risks

- **Cache-singleton regression:** never return fresh engines — route through the cached getters.
- **`AppTest` patch targets:** re-importing the getters into `app.py`'s namespace preserves existing
  patch paths; prefer patching `wherewolf.engines.get_engine` for new tests.
- **Circular imports:** `ui/results.py` must not import `wherewolf.app`; `engines.py` must not import
  `app`. Pass `get_engine` as a parameter.
- **`streamlit` not in `execution`:** keep caching in `engines.py`.
- **Brittle existing test:** do not disturb `test_constants.py::test_supported_extensions`.

---

## Quality Gates

Run before marking any round complete:

```bash
scripts/orchestration/run-quality-gates
scripts/orchestration/check-review-notes-not-deleted
git status --short
```

The round is not complete unless:

1. all requested implementation work is done;
2. all relevant tests pass;
3. build/typecheck gates pass;
4. review notes have not been deleted;
5. the working tree is clean;
6. all code/docs changes are committed.

---

## Verification

1. Automated gates green: `scripts/orchestration/run-quality-gates` (ruff check/format, ty, pytest).
2. **Behavior-parity checklist (must be unchanged):**
   - Schema HUD loads on engine/dataset change.
   - Run / Cancel still work.
   - Truncated-preview "Prepare full export" still re-runs without a row limit.
   - **Target Dialect** translation HUD still renders for a successful query.
   - Query history still records successful runs.
3. Confirm the three duplicated `if engine_name == "DuckDB"` blocks are gone (grep `app.py`) and the
   two inline dialect dicts are replaced by `DIALECT_MAPPING`.

**Deferred verification:** Manual UI smoke testing
(`./run.sh uv run streamlit run src/wherewolf/app.py`) and any user acceptance testing are deferred
until after the base branch is pushed and a release is requested (both opt-in / `ORCH_PUSH=1`).

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished engine-dialect-results-refactor
```

This writes:

```text
/tmp/wherewolf/engine-dialect-results-refactor_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer engine-dialect-results-refactor`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/engine-dialect-results-refactor-review-*.md
```

When a review note exists or a new review note appears:

1. Read the full review note.
2. If the note ends with:

   ```text
   STATUS: CHANGES_REQUESTED
   ```

   then resume work.

3. Clear the round-complete marker:

   ```bash
   scripts/orchestration/clear-finished engine-dialect-results-refactor
   ```

4. Address every requested change.
5. Run quality gates:

   ```bash
   scripts/orchestration/run-quality-gates
   scripts/orchestration/check-review-notes-not-deleted
   ```

6. Commit code/docs fixes.
7. Commit the review-note file itself if it is not already committed:

   ```bash
   git add docs/review/engine-dialect-results-refactor-review-*.md
   git commit -m "docs(review): record engine-dialect-results-refactor review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished engine-dialect-results-refactor
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer engine-dialect-results-refactor` after the next review note is created.

---

## Approval Handling

If the latest review note ends with:

```text
STATUS: APPROVED
```

then:

1. Confirm every previous review item has been addressed.
2. Confirm all review notes are committed:

   ```bash
   scripts/orchestration/check-review-notes-committed engine-dialect-results-refactor
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize engine-dialect-results-refactor
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/engine-dialect-results-refactor_finalized
   ```

6. Stop polling and exit cleanly.

---

## Review Rules

Do not write your own review.

Do not create files under:

```text
docs/review/
```

Do not delete files under:

```text
docs/review/
```

Only the orchestrator writes review notes. Your job is to read them, resolve them, commit them as audit records, and continue the loop.

---

## Finalization Rules

Only finalize after a review note with:

```text
STATUS: APPROVED
```

Finalization is performed with:

```bash
scripts/orchestration/finalize engine-dialect-results-refactor
```

Do not manually merge into `main` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/engine-dialect-results-refactor_finished
/tmp/wherewolf/engine-dialect-results-refactor_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
