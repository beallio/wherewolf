# Plan: Headless DuckDB Query CLI (headless-query-cli)

## Context

### Problem Definition

Wherewolf's engine, catalog, request builder, and full-result exporter are usable without the
desktop, but the console entry point can currently only launch Qt, report a version, or manage the
desktop entry. Users cannot run a checked SQL query over local files from SSH, CI, cron, or a
Makefile.

The current `wherewolf --version` path establishes an important contract: headless commands must
finish without importing Qt or PySpark. `wherewolf.services.__init__` imports `SettingsService` and
therefore Qt; importing any `wherewolf.services.<module>` executes that package initializer first,
so direct submodule imports alone do **not** solve the problem. A runtime probe confirmed that
importing `wherewolf.execution.registry` currently loads PyQt6 through this chain. The package
export must become lazy before the query runner can honestly be headless. The active DuckDB adapter
is request-scoped and already streams full CSV/Parquet export through DuckDB `COPY`; reuse that path
rather than materializing an arbitrarily large frame in Python.

### Intended Outcome

Add this independently usable DuckDB-only v1 command:

```text
wherewolf query SQL [--dataset ALIAS=PATH ...] --format {csv,parquet,xlsx} -o PATH [--force]
```

- `--dataset` is repeatable and optional, allowing both file-backed queries and `SELECT 1`.
- SQL is one command-line argument. SQL files, stdin, named parameters, saved-query lookup, Spark,
  and result streaming to stdout are deferred.
- `--format` defaults to `csv`; `--output/-o` is required. The exact output path is honored rather
  than silently changing its suffix.
- Existing destinations fail closed unless `--force` is supplied. The adapter's atomic writer
  must preserve the old file when query/export fails.
- An output path that resolves to any input dataset is rejected even with `--force`, including
  symlink aliases; a directory is never accepted as output.
- Success writes one `Wrote <absolute-path>` line to stdout and exits 0. Validation or execution
  failures write a concise `wherewolf query: ...` line to stderr, leave stdout empty, and exit 1.
  Argparse syntax errors retain exit 2.
- Existing no-command GUI launch, `--version`, `install-desktop-entry`, and
  `remove-desktop-entry` behavior remains backward compatible.

### Architecture Overview

- Make the `SettingsService` export in `src/wherewolf/services/__init__.py` lazy with
  `TYPE_CHECKING` plus module `__getattr__`, preserving existing
  `from wherewolf.services import SettingsService` callers while allowing service/execution
  submodules to load without Qt. Then restructure `src/wherewolf/cli.py` around argparse subparsers,
  leaving Qt imports inside the GUI-only dispatch branch.
- Add `src/wherewolf/services/headless_query.py` with pure dataset-spec parsing and a
  `HeadlessQueryRunner`. It creates a `CatalogService`, adds each resolved file, renames the entry
  through the service's existing alias validator, builds a DuckDB `ExecutionRequest`, obtains a
  request-scoped adapter from `EngineRegistry`, and invokes its existing full-export capability.
- Define a small structural protocol for the adapter's `export_full` method or use a checked
  `getattr` exactly as `ExportWorker` does. Always close the adapter in `finally`.
- Repair the active adapter's missing JSON Lines branch as part of this plan. The CLI must not
  advertise the repository's accepted `SourceFormat.JSON_LINES` and then parse it as CSV. Dispatch
  `_DuckDBAdapter._register_view` through `SourceFormat.from_path`, matching the already-correct
  legacy engine and removing the silent CSV fallback.

### Core Data Structures

- `HeadlessQueryOptions` frozen dataclass: SQL, tuple of raw dataset specs, `ExportFormat`, output
  `Path`, and overwrite flag.
- Optional `DatasetArgument` frozen dataclass: validated alias and resolved `Path`.
- No persisted data, catalog schema, `ExecutionRequest`, or `QueryResult` shape changes.

### Public Interfaces

- New `query` CLI subcommand and options exactly as shown above.
- `HeadlessQueryRunner.run(options: HeadlessQueryOptions) -> Path` returns the written absolute path
  or raises a user-presentable `ValueError`/runtime exception at the service boundary.
- Dataset syntax splits on the first `=`. Aliases use `CatalogService.rename` validation; paths may
  contain later `=` characters. Duplicate aliases and duplicate resolved paths are errors.
- Query SQL must contain exactly one executable statement. Multi-statement input is rejected before
  adapter creation. One ordinary trailing statement terminator, including before a trailing SQL
  comment, is normalized away before building the export request so valid CLI SQL can be wrapped by
  `COPY`/the XLSX count query. DDL/non-row-producing input is reported as a query/export failure
  without a traceback or partial destination.
- No GUI action and no Python package API compatibility promise beyond the typed service used by
  the CLI tests.

### Dependency Requirements

None. Reuse argparse, pathlib, DuckDB, Polars/PyArrow initialization, `CatalogService`,
`ExecutionRequestBuilder`, `EngineRegistry`, and `ExportFormat`. `pyproject.toml` and `uv.lock` must
not change.

### Scope Boundaries

In scope: lazy Qt service export needed for a real headless boundary, DuckDB query-to-file
execution, explicit dataset aliases, three existing export formats, atomic overwrite/input-source
protection, stable exit/output behavior, and the active-adapter JSONL regression required for
source-format parity.

Out of scope: stdout result data, stdin/SQL-file input, parameters, saved queries, Spark, progress
bars, cancellation/signals, workspace state, catalog persistence, shell completion, and any GUI
changes.

**Slug used throughout this plan:** `headless-query-cli`

---

## Orchestration Contract

**Slug:** `headless-query-cli`

**Plan file:**

```text
docs/plans/2026-08-22_headless-query-cli.md
```

**Implementation branch:**

```text
feat/headless-query-cli
```

**Round-complete marker:**

```text
/tmp/wherewolf/headless-query-cli_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/headless-query-cli_finalized
```

**Review notes:**

```text
docs/review/headless-query-cli-review-*.md
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
git pull --ff-only origin dev
git checkout -b feat/headless-query-cli
```

Commit this plan first:

```bash
git add docs/plans/2026-08-22_headless-query-cli.md
git commit -m "docs(plan): add headless-query-cli implementation plan"
```

---

## Implementation Tasks

Work in order with strict TDD. Add each failing test and observe RED before implementation, then
make the smallest GREEN change. Run project commands through `./run.sh`; keep commits atomic and
Conventional Commit formatted.

### 1. Establish the baseline

Run `git status --short` and `./run.sh uv run pytest -q`. Record the exact suite tally in
`docs/agent_conversations/2026-08-22_headless-query-cli.json`. Stop on a red baseline or unexpected
working-tree changes.

### 2. RED then GREEN: establish a real headless import boundary

Create `tests/test_import_boundaries.py` before changing package exports:

- importing the existing `wherewolf.execution.registry` and
  `wherewolf.services.catalog_service` modules does not add any module beginning with `PyQt6` or
  `pyspark` to `sys.modules`;
- `from wherewolf.services import SettingsService` still resolves the same class and does load Qt
  only when explicitly requested; and
- existing `wherewolf.services` exports remain importable.

Run the import test and record the current PyQt6 failure. Then make only the Qt-backed
`SettingsService` export lazy in `src/wherewolf/services/__init__.py`; preserve its `__all__` entry
and type-checking visibility. Do not make unrelated exports lazy without evidence.

Commit: `refactor(services): keep headless imports free of Qt`.

### 3. RED then GREEN: repair active DuckDB JSON Lines registration

Add a regression to `tests/test_registry.py` that creates a two-line `.jsonl` fixture, builds an
ordinary `ExecutionRequest` through `CatalogService` and `ExecutionRequestBuilder`, executes it via
`EngineRegistry`, and asserts separate typed `id`/payload columns and both rows. Also cover that an
unsupported suffix cannot silently fall through to CSV in `_DuckDBAdapter`.

Run and record the current JSONL failure:

```bash
./run.sh uv run pytest tests/test_registry.py -q --no-cov -k "jsonl or unsupported_suffix"
```

Change `_DuckDBAdapter._register_view` to use `SourceFormat.from_path` and explicit cases for CSV,
Parquet, JSON, JSON Lines, and XLSX. JSON Lines must call parameterized
`read_json_auto(?, format='newline_delimited')`. Remove the fallback CSV branch. Preserve current
absolute-path resolution and identifier-safe `create_view` behavior.

Run the focused registry tests and existing source-format tests. Commit:
`fix(execution): register JSON Lines in the active DuckDB adapter`.

### 4. RED: specify dataset arguments and headless runner safety

Create `tests/test_headless_query.py` before `headless_query.py`. Cover:

- `sales=/path/with=equals.csv` splits only once and resolves the path;
- empty/invalid aliases, missing `=`, missing files, directories, unsupported extensions,
  duplicate aliases case-insensitively, and duplicate resolved paths fail with precise messages;
- zero datasets is valid for a constant query;
- an existing destination fails without `force=True` and its bytes remain unchanged;
- output resolving to an input dataset, including through a symlink, fails even with force; output
  directories fail without modification;
- the requested output path is not suffix-normalized;
- zero/empty and multi-statement SQL are rejected before adapter creation, while a non-row-returning
  statement fails cleanly without creating/replacing the destination;
- a single query with a trailing semicolon, with and without a trailing line comment, exports
  successfully while semicolons inside strings/comments remain unchanged;
- the runner builds a DuckDB request, passes bound catalog aliases to `export_full`, closes its
  adapter after success and failure, and reports the returned absolute destination; and
- an adapter lacking `export_full` fails explicitly rather than with an attribute traceback.

Use fake registries/adapters for lifecycle tests and a real CSV fixture for one integration test.
Run the new module and record its pre-implementation failures:

```bash
./run.sh uv run pytest tests/test_headless_query.py -q --no-cov
```

### 5. GREEN: implement the GUI-free query service

Add `src/wherewolf/services/headless_query.py` with the dataclasses and runner in Context. Import
`CatalogService`, `ExecutionRequestBuilder`, and `ExportFormat` from their concrete modules. Build
catalog entries by calling `add_paths` followed by `rename`, surfacing every warning/duplicate as a
failure; do not duplicate the catalog's alias regex.

Require exactly one non-empty executable SQL statement and a non-directory output path. Derive the
SQL passed to `ExecutionRequestBuilder` from the validated statement span, removing only its final
terminator; do not use a blanket string replacement that can touch literals/comments. Resolve
every source and destination for identity checks; refuse output equal to any input even when forced.
Refuse an existing path unless forced, but leave creation/atomic replacement to the existing
adapter. Build with
`EngineKind.DUCKDB`; `preview_limit` has no output semantics because `export_full` re-executes the
captured SQL. Close the adapter in `finally`, including validation failures after creation.

Do not import anything under `wherewolf.desktop`. Importing concrete service modules is allowed
only after task 2 proves their package initializer remains Qt-free.

Extend `tests/test_import_boundaries.py` now that the module exists: importing
`wherewolf.services.headless_query` must also leave PyQt6 and PySpark absent.

Run `tests/test_headless_query.py` and commit:
`feat(cli): add GUI-free DuckDB query runner`.

### 6. RED: specify CLI grammar, output, exit codes, and lazy imports

Extend `tests/test_cli.py` and `tests/test_version_reporting.py` first:

- no subcommand still delegates to the desktop;
- both desktop-entry subcommands and `--version` remain unchanged;
- `query` passes exact typed options to a fake runner;
- repeatable `--dataset`, default CSV format, all three format choices, `-o`/`--output`, and
  `--force` parse correctly;
- service success prints exactly one destination line and returns 0;
- validation/execution failure prints only the prefixed error on stderr and returns 1;
- missing SQL/output and invalid format remain argparse exit 2; and
- a subprocess with a deliberately unusable Qt platform environment successfully executes a
  constant query while asserting no module beginning `PyQt6` and no `pyspark` module was imported.

Run the focused tests and record their RED failures:

```bash
./run.sh uv run pytest tests/test_cli.py tests/test_version_reporting.py -q --no-cov
```

### 7. GREEN: add the `query` subcommand without regressing legacy dispatch

Refactor `cli.main` to explicit subparsers. Keep global `--version` answerable before any command
dispatch. Construct `HeadlessQueryOptions`, invoke the runner, and normalize only user-facing
exceptions at the CLI boundary. Do not catch `SystemExit` from argparse and do not print a Python
traceback for expected input/query failures.

Run:

```bash
./run.sh uv run pytest tests/test_cli.py tests/test_version_reporting.py \
  tests/test_headless_query.py tests/test_registry.py -q --no-cov
```

Commit: `feat(cli): expose headless query-to-file command`.

### 8. Refactor and document

Keep parser construction readable; extract private helpers rather than letting `main()` become a
large condition chain. Update README with the exact syntax, formats, overwrite behavior, examples,
exit-code contract, and explicit v1 exclusions. Add an `Unreleased` changelog entry. Complete the
session log with files, tests, design decisions, exact tallies, and deferred validation.

Commit: `docs(cli): document headless query mode`.

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

Use `references/verification-standards.md` from the orchestration-plan-author skill. Store command
outputs and exit codes in the session log; do not replace them with prose conclusions.

### Automated acceptance

1. Run focused tests:

   ```bash
   ./run.sh uv run pytest tests/test_cli.py tests/test_version_reporting.py \
     tests/test_import_boundaries.py tests/test_headless_query.py tests/test_registry.py \
     tests/test_full_export.py -q
   ```

2. Run `scripts/orchestration/run-quality-gates`. Any non-zero sub-gate, failed/error tally, or
   dirty generated cache is failure.

3. Run an actual headless subprocess against a disposable CSV under `/tmp/wherewolf/` with
   `QT_QPA_PLATFORM_PLUGIN_PATH` set to a nonexistent directory. Require exit 0, the exact success
   line, an output file containing all expected rows, and no Qt plugin error on stderr.

### Required failure cases and negative control

After the happy-path integration case, run subprocess cases for an invalid alias, missing source,
unsupported source, multi-statement/DDL/bad SQL, missing `-o`, output equal to an input, output
symlinked to an input, output directory, and pre-existing destination without `--force`. Assert the
documented exit code and exact stderr prefix for each. For every existing destination/source case,
assert its original checksum is unchanged; absence of the file is failure, not agreement.

Then rerun a valid `SELECT 1` with no datasets and a valid CSV query after all failure cases. Both
must exit 0 and produce the expected output, proving failure handling did not poison later runs.

### Mutation proof

Temporarily remove the runner's destination-exists guard, run the overwrite-protection test, and
require it to fail because the sentinel file changed or no error was raised. Restore the exact
implementation from a patch stored under `/tmp/wherewolf/headless-query-cli/`, rerun the test, and
require it to pass. Do not use a destructive worktree reset.

Manual validation of cron/systemd configuration, Windows path quoting, Spark, stdout streaming,
stdin/SQL-file input, saved queries, and named parameters is explicitly deferred and must be
recorded as unverified.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished headless-query-cli
```

This writes:

```text
/tmp/wherewolf/headless-query-cli_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer headless-query-cli`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/headless-query-cli-review-*.md
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
   scripts/orchestration/clear-finished headless-query-cli
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
   git add docs/review/headless-query-cli-review-*.md
   git commit -m "docs(review): record headless-query-cli review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished headless-query-cli
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer headless-query-cli` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed headless-query-cli
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize headless-query-cli
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/headless-query-cli_finalized
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
scripts/orchestration/finalize headless-query-cli
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/headless-query-cli_finished
/tmp/wherewolf/headless-query-cli_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
