# Plan: Oracle and PostgreSQL source dialects

Date: 2026-08-02
Branch: `feat/oracle-postgres-dialects` off `dev`
Depends on: `desktop-parity-2` being reviewed and merged first (it edits the same
`main_window.py` region).

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
