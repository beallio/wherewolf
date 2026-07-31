# Plan: PyQt6 Desktop Migration - Foundation (Phases 0-3) (pyqt6-desktop-foundation)

## Context

Wherewolf is a local single-user SQL workbench whose UI is Streamlit. The full
replacement design lives in `docs/plans/2026-07-30-pyqt6-qscintilla-desktop-migration.md`
(the "migration document"). Read Sections 6-9, 18, 19 and Phases 0-3 of Section 20
before starting. **This plan implements only Phases 0-3 of that document** — the
slice the migration document calls "PR 1 — License, contracts, and desktop skeleton".

Everything else in the migration document (catalog, QScintilla editor, formatter,
IntelliSense, execution controller, result grid, history v2, export, optional
Spark, Streamlit removal, release) is **out of scope here** and will be separate
plans. Do not start those phases.

### What this plan delivers

1. **Phase 0** — reproducible baseline, maintainer rights audit, and a proven
   headless PyQt6 + QScintilla dependency set locked into `uv.lock`.
2. **Phase 1** — relicense future releases to `GPL-3.0-only` (required before
   GPL-only Qt bindings ship inside the distributable), preserving accurate MIT
   terms for already-published `0.x` releases.
3. **Phase 2** — UI-neutral domain models, an execution-engine protocol, and an
   engine registry whose availability check does not import PySpark.
4. **Phase 3** — a native `QMainWindow` shell reachable through a **temporary**
   `wherewolf-desktop` console script, with persisted window/dock/splitter state.

### Overriding decisions from the maintainer (these beat the migration document)

- **Target release is a MINOR bump (`0.6.0`), not `1.0.0`.** Migration-document
  Section 19.3 is superseded. **Do not bump the version in this plan at all** —
  `pyproject.toml` stays at `0.5.2`; the bump happens in the final cutover plan.
- **Integration branch is `dev`, not `main`.** The Orchestration Contract below is
  already correct; do not merge to `main`.
- **Relicensing is authorized.** `git shortlog -sne --all` on the baseline shows
  exactly two identities, both David Beall (`6121439+beallio@users.noreply.github.com`,
  134 commits; `beallio@users.noreply.github.com`, 1 commit), and the maintainer
  has confirmed sole copyright. You still must *record* the audit (Task 2); you
  must not re-litigate the decision.

### Hard constraint: Streamlit must keep working for the entire plan

This is a coexistence slice. At every commit:

- `[project.scripts] wherewolf` still points at `wherewolf.cli:main`, which still
  launches Streamlit (`src/wherewolf/cli.py:17`).
- **`src/wherewolf/app.py`, `src/wherewolf/engines.py`, `src/wherewolf/ui/*`,
  `src/wherewolf/export/*`, `src/wherewolf/storage/*` and `.streamlit/` are NOT
  modified by this plan.** They are deleted in the later cutover plan, not here.
- Every currently-passing test must still pass. You are adding a parallel desktop
  code path, not rewiring the existing one.

### Verified facts about the current code — rely on these

- `src/wherewolf/engines.py:6,11` wraps `DuckDBEngine()` / `SparkEngine()` in
  `@st.cache_resource`, so the Streamlit app receives **process-wide singletons**.
  `DuckDBEngine.__init__` opens one persistent `:memory:` connection
  (`src/wherewolf/execution/duckdb_engine.py:13`) and keeps a `_registered_views`
  idempotency map (`:14`); `tests/test_app_cancel.py` depends on `interrupt()`
  reaching that same connection. **The new registry must not replace `engines.py`
  or be wired into `app.py` in this plan** — doing so would re-register views on
  every rerun and break cancellation. Add the registry alongside it.
- `src/wherewolf/execution/__init__.py:3` eagerly imports `SparkEngine`, and
  `src/wherewolf/execution/spark_engine.py:8-13` imports `pyspark.sql` at module
  import time inside a `try/except ImportError`. Therefore **`import wherewolf.execution`
  today imports PySpark.** The new registry must reach engine classes lazily
  (inside `create()`), and must detect Spark availability with
  `importlib.util.find_spec("pyspark")` rather than an import.
- `src/wherewolf/translation/translator.py:33` returns `translated[0]` from
  `sqlglot.transpile(...)`, silently discarding statements 2..N. Migration document
  Sections 12.2 and 14.6 forbid that behavior in the desktop path.
- `pyspark` stays a **mandatory** dependency in this plan. Moving it to an optional
  extra is Phase 13 and would break the Streamlit app's Spark engine now.
- `src/wherewolf/constants.py:4` still advertises `.xls`, which no tested reader
  supports. Removing it from `SUPPORTED_EXTENSIONS` is the catalog phase's job
  (it would change `file_browser.py` behavior and `tests/test_constants.py`).
  **Leave `constants.py` alone.** The new `SourceFormat` enum simply must not
  contain an `.xls` member.

### Repo mechanics that will fail your commits if ignored

- `.git/hooks/pre-commit` runs `./run.sh ruff check .`, `ruff format .`,
  **`ty check .` across the whole repo (tests included, not just `src/`)**,
  `pytest`, then `scripts/check_tdd.sh`.
- `scripts/check_tdd.sh` requires, for every staged `src/**/*.py` file, a test at
  the **flat** path `tests/test_<basename>.py`. It does not understand
  subdirectories. So `src/wherewolf/desktop/main_window.py` requires
  `tests/test_main_window.py`, and `src/wherewolf/execution/registry.py` requires
  `tests/test_registry.py`. **Use flat test filenames throughout this plan.**
  The nested `tests/domain/…` tree sketched in migration-document Section 22.2 is
  deferred; do not create it and do not modify `scripts/check_tdd.sh`.
- A new `src/wherewolf/domain/models.py` collides by basename with the existing
  `src/wherewolf/execution/models.py`, which already owns `tests/test_models.py`.
  Extend that same `tests/test_models.py` file to cover both modules — that
  satisfies the hook and keeps the two `QueryResult` types visible side by side.
- All commands run through `./run.sh` so caches stay under `/tmp/wherewolf`
  (`AGENTS.md` Section 5, `.protocol`).

### Deliberate deviations from the migration document (do not "fix" these)

- `ExecutionEngine` (migration document Section 9.1) is defined here **without**
  `export_full`, because `ExportRequest`/`ExportResult` belong to Phase 12.
- `CompletionContext` / `CompletionItem` (Section 8.5) are Phase 7; not defined here.
- `src/wherewolf/__main__.py` (Section 18.3) is Phase 14; not added here.
- `Translator.translate()` keeps its current first-statement-only behavior because
  the Streamlit app calls it (`src/wherewolf/app.py:412`, `src/wherewolf/ui/results.py:61`).
  Statement preservation arrives as a **new** method, `translate_statements()`.

**Slug used throughout this plan:** `pyqt6-desktop-foundation`

---

## Orchestration Contract

**Slug:** `pyqt6-desktop-foundation`

**Plan file:**

```text
docs/plans/2026-07-31_pyqt6-desktop-foundation.md
```

**Implementation branch:**

```text
feat/pyqt6-desktop-foundation
```

**Round-complete marker:**

```text
/tmp/wherewolf/pyqt6-desktop-foundation_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/pyqt6-desktop-foundation_finalized
```

**Review notes:**

```text
docs/review/pyqt6-desktop-foundation-review-*.md
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
3. Branch from `dev`.
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

## Scope discipline

- Implement only the units the plan lists. Do not modify files outside the plan's scope.
- Do not change runtime behavior beyond what the plan specifies. A `refactor` or
  `cleanup` commit must preserve observable behavior.
- Never edit a test's expected value to make a behavior change pass. If a test
  legitimately must change, that change must be required by the plan or a review
  note, and you must record the rationale in the session log.
- If you spot an unrelated improvement, do not make it here — note it in the
  session log for a separate plan.

---

## Setup

Start from `dev`:

```bash
git checkout dev
# ORCH_LOCAL_ONLY: local trial branch, skipping origin pull
git checkout -b feat/pyqt6-desktop-foundation
```

Commit this plan first:

```bash
git add docs/plans/2026-07-30-pyqt6-qscintilla-desktop-migration.md
git add docs/plans/2026-07-31_pyqt6-desktop-foundation.md
git commit -m "docs(plan): add pyqt6-desktop-foundation implementation plan"
```

---

## Implementation Tasks

Work the tasks in order. Each task is one commit (or a red commit plus a green
commit). Run `./run.sh uv run pytest` after every task, not just at the end.

Record every command's real output in the session log. Do not write "passed" —
write the tally the tool printed.

---

### Task 1 — Baseline and session log (Phase 0)

1. Emit the `AGENT_PROTOCOL_HANDSHAKE` block required by `AGENTS.md` Section 1,
   with every checkbox confirmed, after actually running `pwd`, `ls`,
   `git status`, and inspecting `pyproject.toml` / `uv.lock` / `run.sh` /
   `.protocol`.
2. Create the session log at
   `docs/agent_conversations/2026-07-31_pyqt6-desktop-foundation.md`. It must
   carry the headings required by `AGENTS.md` Section 14: date, task objective,
   files modified, tests added, design decisions, results. Append to it as you go.
3. Capture the baseline **before changing any dependency**:

   ```bash
   set -o pipefail
   ./run.sh uv sync --all-extras --dev
   ./run.sh uv run pytest 2>&1 | tail -20
   ```

   Paste the final pytest summary line into the session log verbatim, together
   with `git rev-parse HEAD`.

   **The measured baseline on `dev` at commit `284befd` is fully green:**

   ```text
   61 passed, 1 skipped
   ```

   Verified on both supported interpreters (3.12 and 3.14), with
   `ruff check`, `ruff format --check` and `ty check src/` all clean.

   **Any failure in your baseline run is a real problem — investigate before
   writing code.** An earlier baseline had three failing Spark tests because no
   JVM was installed; OpenJDK 25 is now present and pyspark 4.2 runs against it.
   If those three reappear:

   ```text
   tests/test_excel_support.py::test_excel_support_spark
   tests/test_multi_dataset.py::test_spark_multi_dataset_join
   tests/test_spark_engine.py::test_spark_get_schema
   ```

   check `command -v java` first — the swallowed exception at
   `src/wherewolf/execution/spark_engine.py:93-95` turns a missing JVM into an
   empty schema DataFrame, so the tests fail on an empty-list assertion instead
   of a clear Spark error. That swallow is a **known defect deferred to Phase 13**
   and is marked as such in the source. Do not fix it in this plan; report the
   environment problem instead.

   **Environment note.** `/tmp` is a quota-limited tmpfs too small for this
   project's `.venv` plus uv cache, so `/tmp/wherewolf` is a symlink to
   `~/.local/state/wherewolf-cache`. All the `AGENTS.md` Section 5 paths still
   read `/tmp/wherewolf` and nothing about the cache policy changes. If a
   sandboxed tool reports "Read-only file system" on `/tmp/wherewolf/.uv_cache`,
   the symlink target has not been granted to the sandbox — `ORCH_ADD_DIRS` in
   `orchestration.conf` already includes it.

Commit: `docs(plan): add pyqt6-desktop-foundation implementation plan` is already
your first commit from Setup. Commit the session log as
`docs: record pyqt6 desktop foundation baseline`.

---

### Task 2 — Maintainer rights audit (Phase 0)

Write `docs/specs/2026-07-31_relicense-rights-audit.md` containing:

1. The literal output of:

   ```bash
   git shortlog -sne --all
   ```

2. A list of non-maintainer contributors. Based on the baseline this list is
   empty; if the command's output disagrees with the Context section above, stop
   and report the discrepancy instead of proceeding to Task 4.
3. The result of searching for copied or vendored third-party code:

   ```bash
   grep -rIl --exclude-dir=.git --exclude-dir=docs -iE 'copyright|SPDX-License-Identifier' . | sort
   ```

   Record every hit and its license. `LICENSE` itself is an expected hit.
4. An explicit line recording that the maintainer (David Beall) confirmed sole
   copyright and authorized relicensing to `GPL-3.0-only`, referencing this plan.

Commit: `docs: record relicensing rights audit`.

---

### Task 3 — PyQt6 + QScintilla dependency spike (Phase 0)

**Red first.** Create `tests/conftest.py` with the offscreen guard, then a
failing spike test. The guard must run before anything imports Qt:

```python
# tests/conftest.py
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
```

Create `tests/test_qt_stack.py` asserting, at minimum:

- `import PyQt6` and `from PyQt6 import Qsci` both succeed;
- a `QApplication` instance exists under the offscreen platform (use `pytest-qt`'s
  `qapp` fixture; do not construct a second `QApplication`);
- a `QsciScintilla` widget can be constructed via `qtbot.addWidget(...)`, accept
  `setText("SELECT 1")`, return that text from `text()`, and be destroyed without
  the test hanging;
- `PyQt6.QtCore.QT_VERSION_STR` is a non-empty string starting with `"6."`.

Run it and confirm it fails with a collection/import error before adding the
dependencies. Record that failure in the session log.

**Green.** Add dependencies through `uv` (never hand-edit `uv.lock`):

```bash
./run.sh uv add 'PyQt6>=6.8,<7' 'PyQt6-QScintilla>=2.14,<3'
./run.sh uv add --dev 'pytest-qt>=4.4,<5'
```

The project targets `requires-python = ">=3.12"` and develops on 3.14. This set
was confirmed to resolve on **both** 3.12 and 3.14: PyQt6 6.11.0,
PyQt6-QScintilla 2.14.1, PyQt6-Qt6 6.11.1, PyQt6-sip 13.11.1, pytest-qt 4.5.0.
If `uv` resolves something different, that is fine — record what it actually
locked. If resolution **fails**, stop and report; do not substitute PySide6 or
another editor widget.

Then confirm the spike passes on both ends of the supported range. **Do not run
the 3.12 check through `./run.sh`**: `run.sh:2` hard-exports
`UV_PROJECT_ENVIRONMENT=/tmp/wherewolf/.venv`, so `./run.sh uv run --python 3.12`
would rebuild the shared 3.14 development environment at 3.12. Use a separate
environment directory while keeping every cache under `/tmp/wherewolf`:

```bash
set -o pipefail
# 3.14 — the normal project environment
./run.sh uv run pytest tests/test_qt_stack.py 2>&1 | tail -5

# 3.12 — an isolated environment, caches still redirected per AGENTS.md Section 5
env UV_PROJECT_ENVIRONMENT=/tmp/wherewolf/.venv312 \
    XDG_CACHE_HOME=/tmp/wherewolf/.cache \
    PYTHONPYCACHEPREFIX=/tmp/wherewolf/__pycache__ \
    TMPDIR=/tmp/wherewolf \
    uv run --python 3.12 pytest tests/test_qt_stack.py 2>&1 | tail -5
```

Both environments already exist on this machine and are warm.

Record both summary lines. Afterwards confirm the main environment is still 3.14:

```bash
interpreter_version=$(./run.sh uv run python -c 'import sys; print("%d.%d" % sys.version_info[:2])')
test "$interpreter_version" = "3.14" || {
  echo "FAIL: project env is $interpreter_version, expected 3.14"; exit 1; }
```

If the 3.12 interpreter cannot be provisioned, say so explicitly in the session
log and in your final report — do not silently skip it, and do not report the
3.14 result as covering both.

Commit: `chore(deps): add PyQt6 QScintilla and pytest-qt`.

---

### Task 4 — Relicense future releases to GPL-3.0-only (Phase 1)

**Red first.** Add `tests/test_licensing.py` asserting:

- `LICENSE` exists and contains both `GNU GENERAL PUBLIC LICENSE` and `Version 3`;
- `LICENSES/MIT-pre-0.6.txt` exists and contains `MIT License` and
  `Copyright (c) 2026 David Beall`;
- `pyproject.toml`, parsed with `tomllib`, has `project.license == "GPL-3.0-only"`;
- `pyproject.toml` `project.license-files` includes `LICENSE`;
- `NOTICE.md` exists and mentions both `GPL-3.0-only` and that releases up to and
  including `0.5.2` remain available under MIT;
- `README.md` contains `GPL-3.0-only` and does **not** contain the string
  `License: MIT` (the old badge).

Run and confirm these fail. Record the failure output.

**Green.**

1. Copy the current MIT text verbatim to `LICENSES/MIT-pre-0.6.txt` **before**
   overwriting `LICENSE`. Preserve the existing copyright line exactly.
2. Replace `LICENSE` with the full, unmodified GNU GPL version 3 text.
3. In `pyproject.toml` `[project]`, add:

   ```toml
   license = "GPL-3.0-only"
   license-files = ["LICENSE", "LICENSES/*"]
   ```

   `hatchling` 1.29.0 is locked, which supports these PEP 639 fields. Do not add a
   `License ::` trove classifier alongside an SPDX expression — that combination
   is rejected by modern build backends.
4. Add `NOTICE.md` stating: future releases are `GPL-3.0-only`; releases through
   `0.5.2` were published under MIT and **those grants remain valid and are not
   revoked**; the MIT text is retained at `LICENSES/MIT-pre-0.6.txt`.
5. Update `README.md`: replace the MIT badge with a GPL-3.0 badge, and add a
   `## License` section matching `NOTICE.md`. Per `AGENTS.md` Section 13, bump the
   `cacheBuster` query parameter on every README image/badge URL (currently `11`)
   to `12`.
6. Add a `## Contributing` line to `README.md` stating that contributions are
   accepted under `GPL-3.0-only`.

Do **not** claim anywhere that prior MIT rights are withdrawn.

Commit: `chore!: relicense future Wherewolf releases under GPL-3.0-only`.

---

### Task 5 — UI-neutral domain models (Phase 2)

**Red first.** Extend `tests/test_models.py` (do not create a new file — see
Context) with cases for the new module. Keep the existing tests for
`wherewolf.execution.models.QueryResult` untouched and passing. Assert:

- `EngineKind`, `SourceFormat`, `ExecutionStatus`, `CompletionKind` are `StrEnum`s
  with exactly the members listed in migration-document Section 8.1;
- `SourceFormat` has **no** `.xls`-related member, and
  `SourceFormat.from_path(Path("a.XLSX"))` resolves case-insensitively to
  `SourceFormat.XLSX` while `SourceFormat.from_path(Path("a.xls"))` raises
  `UnsupportedFormatError`;
- `ExecutionRequest`, `QueryResult`, `CatalogEntry`, `CatalogBinding`,
  `ColumnSchema`, `SchemaResult`, `SqlDiagnostic` are frozen — assigning any
  field raises `dataclasses.FrozenInstanceError`;
- `wherewolf.domain.models.QueryResult` and
  `wherewolf.execution.models.QueryResult` are **distinct classes**
  (`assert domain.QueryResult is not execution.QueryResult`), so the coexistence
  is deliberate and visible;
- a `CatalogEntry` whose `path` is later mutated on the *source* object cannot
  affect a previously taken `CatalogBinding` (the binding is an independent frozen
  value, not a reference into live state);
- `QueryResult` with `status=ExecutionStatus.FAILED` carries a non-`None`
  `error_type` and `error_message` and a `frame` of `None`; constructing a
  "successful" result with `frame=None` is rejected. An import failure must never
  be representable as a successful empty frame.

**Green.** Create:

- `src/wherewolf/domain/__init__.py`
- `src/wherewolf/domain/enums.py` — the four enums from Section 8.1, plus a
  `SourceFormat.from_path` classmethod and a single centralized mapping from
  `EngineKind` to its SQLGlot dialect name.
- `src/wherewolf/domain/errors.py` — a `WherewolfError` base plus at least
  `UnsupportedFormatError`, `EngineUnavailableError`, `TranslationError`. These
  must not subclass any Qt or Streamlit type.
- `src/wherewolf/domain/models.py` — the frozen slotted dataclasses from
  migration-document Sections 8.2, 8.3 and 8.4 (`ColumnSchema`, `CatalogEntry`,
  `CatalogBinding`, `ExecutionRequest`, `QueryResult`, `SchemaResult`,
  `SqlDiagnostic`). Enforce the success/failure invariant in `__post_init__`.

`check_tdd.sh` needs `tests/test_enums.py` and `tests/test_errors.py` for the two
new basenames; write real assertions in them, not re-exports of Task 5's tests.

**No module under `src/wherewolf/domain/` may import `PyQt6`, `streamlit`,
`duckdb`, or `pyspark`.** Add a test asserting this by importing
`wherewolf.domain.models` in a subprocess and checking `sys.modules`.

Commit: `feat(domain): add UI-neutral execution and catalog models`.

---

### Task 6 — Execution engine protocol (Phase 2)

**Red first.** Add `tests/test_base.py` asserting:

- `CancellationHandle` and `ExecutionEngine` are `typing.Protocol`s and are
  `runtime_checkable`;
- a minimal in-test fake implementing `execute_preview`, `inspect_schema`,
  `cancellation_handle` and `close` satisfies `isinstance(fake, ExecutionEngine)`;
- an object missing `close` does **not** satisfy it;
- importing `wherewolf.execution.base` in a subprocess leaves `PyQt6`,
  `streamlit` and `pyspark` absent from `sys.modules`.

**Green.** Create `src/wherewolf/execution/base.py` with `CancellationHandle` and
`ExecutionEngine` exactly as in migration-document Section 9.1 **minus
`export_full`** (see Context deviations). Do not modify
`src/wherewolf/execution/__init__.py` — adding `base` to its eager imports is
unnecessary and risks perturbing the Streamlit import graph.

Commit: `feat(execution): add UI-neutral engine and cancellation protocols`.

---

### Task 7 — Engine registry with lazy Spark detection (Phase 2)

**Red first.** Add `tests/test_registry.py` asserting:

- `EngineRegistry().available_engines()` returns a tuple of `EngineDescriptor`
  values that always includes DuckDB;
- the Spark descriptor's `available` flag is driven by
  `importlib.util.find_spec("pyspark")`, verified by monkeypatching `find_spec`
  to return `None` and asserting the descriptor reports unavailable **with a
  human-readable reason string**, not by omitting Spark from the list;
- **the critical one:** running

  ```python
  import sys, wherewolf.execution.registry as r
  r.EngineRegistry().available_engines()
  assert "pyspark" not in sys.modules
  ```

  in a **subprocess** (`subprocess.run([sys.executable, "-c", ...])`) exits 0.
  It must be a subprocess: the pytest process itself has already imported
  `pyspark` via other tests, so an in-process `sys.modules` check would pass
  vacuously. Assert on the subprocess's exact stderr when it fails, not merely
  on a non-zero exit code (a missing interpreter also exits non-zero).
- `create(EngineKind.DUCKDB, request_id)` returns an object satisfying
  `isinstance(obj, ExecutionEngine)`;
- `create(EngineKind.SPARK, request_id)` raises `EngineUnavailableError` with an
  actionable message when `find_spec("pyspark")` is patched to `None`;
- each `create()` call for DuckDB returns a **new** object
  (`assert a is not b`) — the registry is not a singleton cache.

**Green.** Create `src/wherewolf/execution/registry.py` with `EngineDescriptor`
(kind, display name, available, unavailable reason) and `EngineRegistry`.
Import engine classes **inside** `create()`, never at module scope.

Existing `DuckDBEngine`/`SparkEngine` do not yet implement `execute_preview` /
`inspect_schema` / `cancellation_handle`. Wrap them in thin request-scoped
adapters inside `registry.py` (or a sibling module with its own flat test file)
that satisfy the protocol by delegating to the current `execute()` / `get_schema()`
/ `interrupt()` methods and translating the legacy mutable `QueryResult` into the
new frozen `wherewolf.domain.models.QueryResult`. **Do not modify
`duckdb_engine.py` or `spark_engine.py`** — the request-scoped connection rewrite
is Phase 8.

Commit: `feat(execution): add lazy UI-neutral engine registry`.

---

### Task 8 — Statement-preserving translation (Phase 2)

**Red first.** Extend `tests/test_translator.py` asserting:

- `Translator().translate_statements("SELECT 1; SELECT 2", "duckdb", "spark")`
  returns a tuple of length **2**;
- a single statement returns a tuple of length 1;
- an empty or whitespace-only query returns an empty tuple;
- an unsupported dialect raises `ValueError` (unchanged behavior);
- unparseable SQL raises `TranslationError` (from `wherewolf.domain.errors`)
  whose message includes the underlying SQLGlot message;
- **regression pin:** the legacy `translate()` still returns only the first
  statement for `"SELECT 1; SELECT 2"`, with a comment in the test naming this as
  deliberate Streamlit-era behavior removed at cutover.

**Green.** Add `translate_statements()` to
`src/wherewolf/translation/translator.py`. Do not change `translate()`'s
behavior or signature. Do not change the existing `VALID_DIALECTS` set.

Commit: `feat(translation): preserve every statement in translate_statements`.

---

### Task 9 — Settings service (Phase 3)

**Red first.** Add `tests/test_settings_service.py`. Use
`QSettings.setDefaultFormat(QSettings.Format.IniFormat)` plus a `tmp_path`
`QSettings.setPath(...)` (or an injected `QSettings` instance) so tests never
touch the developer's real settings. Assert:

- a geometry/state round trip returns the same bytes;
- reading a key that was never written returns the documented default rather
  than raising;
- a **corrupt** stored value (write a garbage string where `QByteArray` geometry
  is expected) causes only that key to fall back to its default, while a
  neighbouring valid key still returns its stored value — proving the reset is
  scoped, not global;
- the settings keys are namespaced with an explicit schema version.

**Green.** Create `src/wherewolf/services/__init__.py` and
`src/wherewolf/services/settings_service.py` wrapping `QSettings`. Set the
organization/application names from migration-document Section 16.3. Persist only
the Phase 3 subset: main-window geometry, window state (docks/toolbars), splitter
sizes, and editor font size. Do not persist query history.

`check_tdd.sh` maps `settings_service.py` to `tests/test_settings_service.py` —
the names already match.

Commit: `feat(desktop): add QSettings-backed settings service`.

---

### Task 10 — Native application shell (Phase 3)

**Red first.** Add `tests/test_main_window.py` and `tests/test_actions.py` using
`pytest-qt`'s `qtbot`. Assert:

- constructing `MainWindow` yields exactly one `QMainWindow` with a menu bar, a
  primary toolbar, a left dataset-catalog dock, a central splitter, a bottom
  `QTabWidget`, and a status bar;
- the menu bar has top-level `File`, `Edit`, `Query`, `View`, `Help` menus;
- the `Run` action is **enabled** and the `Cancel` action is **disabled** at
  startup (migration document Section 14.1);
- `Format SQL`, `Run`, and `Cancel` each exist as a **single shared `QAction`
  object** — assert the toolbar's action and the menu's action are the *same*
  object (`is`), not two equal ones;
- the Query menu's Run action carries a `Ctrl+Return` shortcut and Cancel carries
  `Ctrl+.`;
- restoring geometry from a deliberately corrupt settings value leaves the window
  constructible and visible rather than raising;
- `close()` on the window leaves no top-level widgets alive.

Actions that have no Phase-3 implementation (`Format SQL`, `Add Datasets…`, etc.)
must be present but **disabled**, with an explanatory tooltip naming the phase
that enables them. Do not connect them to empty handlers that silently do nothing.

**Green.** Create:

- `src/wherewolf/desktop/__init__.py`
- `src/wherewolf/desktop/actions.py` — one factory that builds every `QAction`
  once and hands the same objects to menus and toolbars.
- `src/wherewolf/desktop/main_window.py` — the `QMainWindow` layout from
  migration-document Section 10.1, wired to `SettingsService` for save/restore
  on `closeEvent`.
- `src/wherewolf/desktop/application.py` — `main()` that creates the
  `QApplication`, sets organization/application names, shows `MainWindow`, and
  returns `app.exec()`'s exit code.

Use the platform style; add no QSS beyond what a test asserts.

Commit: `feat(desktop): add native PyQt6 application shell`.

---

### Task 11 — Temporary entry point and headless CI (Phase 3)

**Red first.** Add to `tests/test_cli.py` — and **delete the existing
`test_cli_placeholder` stub**, which is exactly the kind of always-true test
`AGENTS.md` and the migration document forbid. Assert:

- `pyproject.toml` (parsed with `tomllib`) has
  `project.scripts.wherewolf-desktop == "wherewolf.desktop.application:main"`;
- `project.scripts.wherewolf` is **still** `wherewolf.cli:main` — the Streamlit
  entry point is untouched in this plan;
- calling `wherewolf.desktop.application.main()` with `QApplication.exec`
  monkeypatched to return `0` returns `0` and constructs exactly one main window
  (no real event loop);
- importing `wherewolf.desktop.application` in a **subprocess** leaves
  `streamlit` and `pyspark` out of `sys.modules` (migration document Section 18.4).
  Assert on the subprocess's stderr text on failure, per Task 7.

**Green.**

1. Add to `pyproject.toml`:

   ```toml
   [project.scripts]
   wherewolf = "wherewolf.cli:main"
   wherewolf-desktop = "wherewolf.desktop.application:main"
   ```

2. Update `.github/workflows/ci.yml` so the Qt tests can run headlessly on the
   Ubuntu runners. In **both** the `lint` and `test` jobs, before the dependency
   install step, add the Qt platform libraries:

   ```yaml
      - name: Install Qt offscreen system libraries
        run: |
          sudo apt-get update
          sudo apt-get install -y libegl1 libgl1 libxkbcommon-x11-0 libdbus-1-3
   ```

   `tests/conftest.py` from Task 3 already exports `QT_QPA_PLATFORM=offscreen`,
   so no workflow-level `env:` entry is needed; do not add one. Leave the
   cross-platform smoke matrix and the Spark job for Phase 15.
3. Update `README.md`: document that `wherewolf-desktop` launches the in-progress
   native application while `wherewolf` still launches the Streamlit UI, and state
   that `wherewolf-desktop` is temporary and will become `wherewolf` at cutover.

Commit: `feat(desktop): add temporary wherewolf-desktop entry point`.

---

### Task 12 — Close out the session log

Append to `docs/agent_conversations/2026-07-31_pyqt6-desktop-foundation.md`:

- every file added/modified, grouped by task;
- the dependency versions `uv` actually locked;
- the pytest tallies from the baseline run and the final run;
- every design decision where you deviated from this plan, with the reason;
- anything you could not verify in this environment (see Verification).

Commit: `docs: close out pyqt6 desktop foundation session log`.

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

These steps are written to the standard in
`~/.claude/skills/orchestration-plan-author/references/verification-standards.md`:
every step below can fail, and each one states what failure looks like. Run them
in order — the mutation checks (V5) deliberately break the tree, and V6 is the
negative control that must run **after** the tree is restored.

Record actual output. Do not paraphrase a result as "passed".

### V1 — Full quality gate

```bash
set -o pipefail
cd "$(git rev-parse --show-toplevel)"
./run.sh uv run pytest 2>&1 | tail -20
```

Record the final summary line verbatim and compare it against the Task 1 baseline
of `61 passed, 1 skipped`.

**Pass condition:** zero failures, zero collection errors, and a passed count
strictly greater than 61 — you are adding tests, so the total must rise.

**Failure looks like:** any failing test at all, or a passed count at or below 61
(tests disappeared or were disabled), or `error` during collection. The baseline
is fully green, so there is no allowlist and nothing to excuse.

Verify mechanically rather than by eye:

```bash
set -o pipefail
cd "$(git rev-parse --show-toplevel)"

output=$(./run.sh uv run pytest -q 2>&1)
printf '%s\n' "$output" | tail -5

failed=$(printf '%s\n' "$output" | awk '/^FAILED /{print $2}')
if [ -n "$failed" ]; then
  echo "FAIL: the baseline is green, so any failure is a regression:"
  printf '%s\n' "$failed"
  exit 1
fi

passed=$(printf '%s\n' "$output" | grep -oE '[0-9]+ passed' | tail -1 | cut -d' ' -f1)
if [ -z "$passed" ] || [ "$passed" -le 61 ]; then
  echo "FAIL: passed count is '${passed:-<none>}', expected greater than 61"
  exit 1
fi
echo "OK: 0 failures; $passed passed (baseline 61)"
```

The `output=$(...)` standalone assignment is deliberate: it propagates the
pipeline's status, unlike embedding the substitution in an outer command
(verification-standards VS-06). The empty-string guard on `$passed` means a
mangled summary line cannot pass vacuously (VS-14).

Then:

```bash
scripts/orchestration/run-quality-gates
```

This runs `scripts/orchestration-hooks/quality-gates`, which is `ruff check
--fix`, `ruff format`, `ty check src/`, and `pytest`. **It must exit 0.** All four
are clean on the baseline.

**Failure looks like:** a non-zero exit from any of the four. Record the last 20
lines of whatever failed.

Note that `ruff` is pinned to the 0.16 default rule set, which is considerably
wider than pre-0.16 (it includes `I`, `BLE`, `UP`, `SIM`, `RUF`, `DTZ`, `B`,
`PIE`). New code must satisfy all of it. In particular, any `except Exception`
you add will trip `BLE001`; if the broad catch is a deliberate boundary that
converts failures into a returned status, annotate it with `# noqa: BLE001` and a
one-line site-specific reason, matching the existing convention in
`src/wherewolf/execution/`. Do not add a blanket ignore.

### V2 — Streamlit path is provably untouched

```bash
set -o pipefail
cd "$(git rev-parse --show-toplevel)"
git diff --name-only "$(git merge-base HEAD dev)"..HEAD -- \
  src/wherewolf/app.py src/wherewolf/engines.py src/wherewolf/ui/ \
  src/wherewolf/export/ src/wherewolf/storage/ src/wherewolf/constants.py .streamlit/
```

**Expected output: nothing at all.** Any filename printed here means the plan's
hard constraint was violated; revert that file before continuing.

Then run the Streamlit-facing suites explicitly:

```bash
set -o pipefail
./run.sh uv run pytest tests/test_app.py tests/test_app_flow.py \
  tests/test_app_cancel.py tests/test_engines.py tests/test_constants.py \
  tests/test_config_toml.py 2>&1 | tail -10
```

**Failure looks like:** any non-zero exit. These suites exercise
`@st.cache_resource` singletons and `interrupt()` on the shared DuckDB
connection; a failure here means the registry work leaked into the Streamlit path.

### V3 — Headless Qt actually renders a window and an editor

```bash
set -o pipefail
./run.sh uv run pytest tests/test_qt_stack.py tests/test_main_window.py \
  tests/test_actions.py tests/test_settings_service.py -v 2>&1 | tail -30
```

Record each test's `PASSED`/`FAILED` line. **Failure looks like:** a hang (the
offscreen platform not being applied — check that `tests/conftest.py` sets
`QT_QPA_PLATFORM` before any Qt import), an `xcb`/`libEGL` plugin error, or a
`QsciScintilla` import error.

Confirm no Qt cache escaped the repo:

```bash
git status --short
```

**Failure looks like:** any untracked `.cache/`, `__pycache__/`, or `.qt/`
directory inside the repository (`AGENTS.md` Section 5).

### V4 — License metadata survives a real build

Build and read the metadata out of the produced wheel — do not assert on
`pyproject.toml` alone, since a build backend can drop or rewrite fields:

```bash
set -o pipefail
cd "$(git rev-parse --show-toplevel)"
rm -rf dist
./run.sh uv build
wheel_path=$(ls dist/wherewolf-*.whl)
metadata=$(unzip -p "$wheel_path" '*.dist-info/METADATA')
printf '%s\n' "$metadata" | grep -E '^License(-Expression|-File)?:'
```

Note the standalone `metadata=$(...)` assignment: it propagates `unzip`'s exit
status, unlike embedding the substitution inside `printf`.

**Expected:** a `License-Expression: GPL-3.0-only` line and `License-File` lines
covering `LICENSE` and `LICENSES/MIT-pre-0.6.txt`. **Failure looks like:** a
`License: MIT` line, a missing `License-Expression`, or `grep` finding nothing.

Confirm the version was **not** bumped:

```bash
version=$(./run.sh uv version --short)
test "$version" = "0.5.2" || { echo "FAIL: version is $version, expected 0.5.2"; exit 1; }
```

**Failure looks like:** the explicit `FAIL:` line above. The version bump belongs
to the cutover plan, not this one.

### V5 — Mutation checks: prove the new tests actually bite

Each mutation below must make a **named** test fail. If a mutation leaves the
suite green, the corresponding test is decoration and must be rewritten before
the round is marked complete.

Run these one at a time, reverting fully between each with
`git checkout -- <file>` and confirming `git status --short` is clean.

1. **Registry laziness.** Add `import pyspark` as the first line of
   `src/wherewolf/execution/registry.py`.

   ```bash
   ./run.sh uv run pytest tests/test_registry.py 2>&1 | tail -15
   ```

   **Expected: the subprocess `sys.modules` test FAILS.** If it passes, the check
   is running in-process (where `pyspark` is already imported by other tests) and
   is vacuous — rewrite it as a real subprocess assertion.

2. **Model immutability.** In `src/wherewolf/domain/models.py`, change
   `ExecutionRequest`'s decorator from `@dataclass(frozen=True, slots=True)` to
   `@dataclass(slots=True)`.

   ```bash
   ./run.sh uv run pytest tests/test_models.py 2>&1 | tail -15
   ```

   **Expected: the `FrozenInstanceError` test FAILS.**

3. **License metadata.** In `pyproject.toml`, change `license = "GPL-3.0-only"`
   to `license = "MIT"`.

   ```bash
   ./run.sh uv run pytest tests/test_licensing.py 2>&1 | tail -15
   ```

   **Expected: the SPDX assertion FAILS.**

4. **Entry point.** Delete the `wherewolf-desktop` line from
   `[project.scripts]` in `pyproject.toml`.

   ```bash
   ./run.sh uv run pytest tests/test_cli.py 2>&1 | tail -15
   ```

   **Expected: the entry-point assertion FAILS.**

5. **Action initial state.** In `src/wherewolf/desktop/main_window.py`, make the
   Cancel action enabled at startup.

   ```bash
   ./run.sh uv run pytest tests/test_main_window.py 2>&1 | tail -15
   ```

   **Expected: the initial-state assertion FAILS.**

Record, for each of the five, the exact test node ID that failed. Then restore:

```bash
git checkout -- pyproject.toml src/wherewolf/
git status --short
```

**`git status --short` must print nothing.** If it prints anything, a mutation
was not reverted — stop and clean up before V6.

### V6 — Negative control (runs last, after V5 is reverted)

```bash
set -o pipefail
cd "$(git rev-parse --show-toplevel)"
./run.sh uv run pytest 2>&1 | tail -20
./run.sh uv run ruff check .
./run.sh uv run ruff format --check .
./run.sh uv run ty check src/
scripts/orchestration/check-review-notes-not-deleted
git status --short
```

Re-run the V1 mechanical check here too, and additionally confirm
`scripts/orchestration/run-quality-gates` exits 0.

This passes only if the implementation is present *and* correct: V5 has just
demonstrated that removing any one of the five load-bearing behaviors turns the
suite red, so a green run here is not something an empty implementation could
produce. Record the summary line and confirm `git status --short` is empty.

### Deferred and explicitly NOT verified

State all of the following in your final report and in the session log. An
unstated gap reads as a covered one.

- **No native window was ever displayed.** Every Qt test runs under
  `QT_QPA_PLATFORM=offscreen`. That a real window appears, is themed by the OS,
  and restores its geometry across an actual restart is **manual, deferred**
  verification. Note it as unverified unless you actually ran
  `wherewolf-desktop` on a display and say so.
- **macOS and Windows are entirely unverified.** CI in this plan is Ubuntu-only;
  the cross-platform smoke matrix is Phase 15.
- **Python 3.12 spike result.** If Task 3 could not provision a 3.12
  interpreter, say so explicitly rather than reporting the 3.14 result as
  covering both ends of the supported range.
- **No query executes in the desktop app.** Phase 3 ships a shell only. Run,
  Cancel, and Format SQL are present-but-disabled; the execution controller is
  Phase 8. Do not describe the desktop app as functional.
- **QScintilla is only smoke-tested.** Task 3 proves the widget constructs and
  round-trips text. Syntax highlighting, completion and formatting are Phases 5-7.
- **CI is not proven green by this plan.** `.github/workflows/ci.yml` is edited
  but cannot run locally; per verification-standards VS-13, a `grep` of the YAML
  is not evidence that CI passes. Report the workflow change as **unverified
  until the first push to `dev`**, and say so plainly.
- **Nothing is published.** No tag, no PyPI upload, no push to `origin`
  (`ORCH_LOCAL_ONLY=1`). The wheel built in V4 is a local artifact; delete `dist/`
  before marking the round complete.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished pyqt6-desktop-foundation
```

This writes:

```text
/tmp/wherewolf/pyqt6-desktop-foundation_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer pyqt6-desktop-foundation`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/pyqt6-desktop-foundation-review-*.md
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
   scripts/orchestration/clear-finished pyqt6-desktop-foundation
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
   git add docs/review/pyqt6-desktop-foundation-review-*.md
   git commit -m "docs(review): record pyqt6-desktop-foundation review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished pyqt6-desktop-foundation
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer pyqt6-desktop-foundation` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed pyqt6-desktop-foundation
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize pyqt6-desktop-foundation
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/pyqt6-desktop-foundation_finalized
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
scripts/orchestration/finalize pyqt6-desktop-foundation
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/pyqt6-desktop-foundation_finished
/tmp/wherewolf/pyqt6-desktop-foundation_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
