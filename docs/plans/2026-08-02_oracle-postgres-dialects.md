# Plan: Oracle and PostgreSQL source dialects (oracle-postgres-dialects)

## Context

## Problem Definition

Wherewolf lets a user write SQL in one dialect and run it against a local engine,
transpiling in between. Today the source-dialect selector offers only three options:

```python
# src/wherewolf/constants.py:7
DIALECT_MAPPING = {"DuckDB": "duckdb", "Spark": "spark", "Azure SQL": "tsql"}
```

Users with Oracle and PostgreSQL SQL cannot paste their queries and run them.

**Execution backends are explicitly unchanged.** DuckDB and Spark remain the only
engines. Oracle and PostgreSQL are *languages you write in*, not databases you connect
to. Nothing in this plan may add a backend, a driver, a connection string, or a network
dependency. `EngineKind` keeps exactly two members.

## Architecture Overview

The dialect and engine axes are already separate: `ExecutionRequest.source_dialect` is a
free-form string fed to `sqlglot`, while `EngineKind` selects the executor. Adding source
dialects is therefore a data change plus tests — no new layer, no new dependency.

`ExecutionRequestBuilder.build` already transpiles when
`source_dialect.lower() != target_dialect.lower()` (`execution_request_builder.py:31`),
so the mechanism exists and is proven: round one verified `tsql` → `duckdb` converts
`SELECT TOP 3` into `LIMIT 3`.

## Core Data Structures

`DIALECT_MAPPING` gains two entries:

```python
DIALECT_MAPPING = {
    "DuckDB": "duckdb",
    "Spark": "spark",
    "Azure SQL": "tsql",
    "Oracle": "oracle",
    "PostgreSQL": "postgres",
}
```

Both identifiers were verified present in `sqlglot.dialects.dialect.Dialects` — not
assumed. No other data structure changes.

## Public Interfaces

No signature changes. `DIALECT_MAPPING` is the only public surface affected, and it is
already consumed generically at `main_window.py:231`, so the selector picks the new
entries up without further wiring. The translation panel already offers sqlglot's full
33-dialect list, so Oracle and PostgreSQL are available as translation *targets* today —
confirm this rather than re-implementing it.

## Dependency Requirements

None. `sqlglot>=30.11.0` is already a direct dependency and ships both dialects.

## The trap this plan must handle

Transpilation succeeding is **not** the same as the query running. Measured against the
installed sqlglot:

| source | input | transpiled to duckdb | runs? |
|---|---|---|---|
| oracle | `SELECT NVL(name,'x') FROM emp` | `SELECT COALESCE(name, 'x') FROM emp` | yes |
| postgres | `SELECT id::text FROM t` | `SELECT CAST(id AS TEXT) FROM t` | yes |
| postgres | `SELECT NOW() - INTERVAL '1 day'` | `SELECT CURRENT_TIMESTAMP - INTERVAL '1' DAY` | yes |
| oracle | `SELECT SYSDATE FROM DUAL` | `SELECT CURRENT_TIMESTAMP AT TIME ZONE 'UTC' FROM DUAL` | **no — DuckDB has no DUAL** |
| oracle | `... WHERE ROWNUM <= 3` | `... WHERE ROWNUM <= 3` | **no — ROWNUM passes through** |

`NVL`, `::` casts, `ILIKE` and interval arithmetic convert correctly. `DUAL` and `ROWNUM`
are emitted verbatim and then fail at the engine with a confusing "column ROWNUM not
found". A user will read that as "Wherewolf's Oracle support is broken."

So the feature is not done when the dropdown has two more entries. It is done when the
user understands why an Oracle-idiomatic query failed.


**Slug used throughout this plan:** `oracle-postgres-dialects`

---

## Orchestration Contract

**Slug:** `oracle-postgres-dialects`

**Plan file:**

```text
docs/plans/2026-08-02_oracle-postgres-dialects.md
```

**Implementation branch:**

```text
feat/oracle-postgres-dialects
```

**Round-complete marker:**

```text
/tmp/wherewolf/oracle-postgres-dialects_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/oracle-postgres-dialects_finalized
```

**Review notes:**

```text
docs/review/oracle-postgres-dialects-review-*.md
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
git checkout -b feat/oracle-postgres-dialects
```

Commit this plan first:

```bash
git add docs/plans/2026-08-02_oracle-postgres-dialects.md
git commit -m "docs(plan): add oracle-postgres-dialects implementation plan"
```

---

## Implementation Tasks

Work the five tasks below in order, TDD throughout: failing test first, then implement.
**One commit per task** — the previous round collapsed eight tasks into a single commit,
which the maintainer accepted once but which is not the standard.

The binding rule from both earlier rounds still applies: a test must reach the feature
from `MainWindow` the way a user would.

## Testing Strategy

**Task 1 — add the dialects.** `tests/test_constants.py:16` currently pins the mapping as
a literal:

```python
assert DIALECT_MAPPING == {"DuckDB": "duckdb", "Spark": "spark", "Azure SQL": "tsql"}
```

Replace it with property assertions — every value resolves to a real `sqlglot` dialect,
Oracle and PostgreSQL are present, and the mapping contains no engine that isn't
DuckDB/Spark. A literal-equality test has to be edited every time the list grows, which
is how it stops being a guard. This mirrors the CI-workflow test rewrite from the
release-candidate work.

**Task 2 — prove transpilation reaches the engine.** For each new dialect, assert through
`ExecutionRequestBuilder.build` that `executable_sql` differs from `original_sql` in the
specific way expected — `NVL` becomes `COALESCE`, `::text` becomes a `CAST` — for both
`EngineKind.DUCKDB` and `EngineKind.SPARK`. Assert on the transformation, not that a
string changed.

**Task 3 — end-to-end execution.** Run a real Oracle-dialect and a real PostgreSQL-dialect
query against DuckDB through the normal request path with a small CSV, and assert on the
returned rows. This is the test that would catch a dialect that transpiles but produces
SQL the engine rejects.

**Task 4 — the untranslatable-construct diagnostic.** Add a test asserting that a query
using `ROWNUM` or `DUAL` under the Oracle dialect produces a *clear* message naming the
construct, rather than a raw engine error. Implement whatever surfaces that — a
pre-execution check against a small set of known-untranslatable constructs, reported
through the existing `MessagesPanel` diagnostics path. Keep the set small and honest; do
not attempt to rewrite Oracle semantics.

**Task 5 — guard the backend boundary.** A test asserting `EngineKind` has exactly the
members `DUCKDB` and `SPARK`, and that the engine selector offers only those two, so a
later change cannot quietly turn a language option into a claimed backend. This is the
test that keeps the stated scope enforced rather than remembered.

**Negative controls (mandatory).** Remove `"Oracle"` from the mapping and confirm the
dialect tests fail. Break the transpile call and confirm task 2 fails. Add a fake third
member to `EngineKind` and confirm task 5 fails. Each mutation should fail its own test
and leave the rest green.

### Cross-cutting requirements

- Do not add an Oracle or PostgreSQL **backend**, driver, connection string, or any
  network dependency. `EngineKind` keeps exactly `DUCKDB` and `SPARK`.
- Do not weaken, skip or delete any existing test.
- Do not remove `timid = true`, the `pyarrow` import in `execution/registry.py`, or
  reintroduce `DontConfirmOverwrite`.
- Do not bump the version, tag, or touch `main`.
- Run `./run.sh uv run ty check .` (whole repo, not just `src/`) before committing — a
  `src/`-only check passes while the pre-commit hook fails on `tests/`.

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

```bash
./run.sh uv run ruff check . && ./run.sh uv run ruff format --check .
./run.sh uv run ty check .          # whole repo — the pre-commit hook does, and src/-only passes while it fails
./run.sh uv run pytest
```

Record in the session log: the selector's full item list with `itemData` values; the
transpiled output for one Oracle and one PostgreSQL query against both engines; the row
data returned by the end-to-end run; and the diagnostic text produced for a `ROWNUM`
query.

## Deferred

No Oracle or PostgreSQL *server* is contacted at any point, so dialect fidelity is only
as good as sqlglot's. Constructs beyond the small documented set will still fail at the
engine — that is a documented limitation, not a defect, and the README should say so
plainly rather than implying full Oracle/PostgreSQL compatibility.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished oracle-postgres-dialects
```

This writes:

```text
/tmp/wherewolf/oracle-postgres-dialects_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer oracle-postgres-dialects`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/oracle-postgres-dialects-review-*.md
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
   scripts/orchestration/clear-finished oracle-postgres-dialects
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
   git add docs/review/oracle-postgres-dialects-review-*.md
   git commit -m "docs(review): record oracle-postgres-dialects review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished oracle-postgres-dialects
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer oracle-postgres-dialects` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed oracle-postgres-dialects
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize oracle-postgres-dialects
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/oracle-postgres-dialects_finalized
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
scripts/orchestration/finalize oracle-postgres-dialects
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/oracle-postgres-dialects_finished
/tmp/wherewolf/oracle-postgres-dialects_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
