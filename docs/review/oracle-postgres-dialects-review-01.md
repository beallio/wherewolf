# Review — oracle-postgres-dialects (round 01)

Branch: `feat/oracle-postgres-dialects` @ `646503a`
Reviewed against: `docs/plans/2026-08-02_oracle-postgres-dialects.md`

## Verdict

APPROVED. Five tasks, five commits — the atomic-commit standard is back.

## The constraint that mattered most

Oracle and PostgreSQL are **languages you write in, not backends you connect to**, and
that boundary is now enforced by the suite rather than remembered:

```text
EngineKind members       ['duckdb', 'spark']
engine selector offers   ['duckdb', 'spark']
```

Adding a fake `ORACLE = "oracle"` member to `EngineKind` fails the boundary test — so a
later change cannot quietly promote a language option into a claimed backend. No driver,
connection string, or network dependency was added.

## Reachability and transpilation, measured by review

Source dialects offered by `input_dialect_selector`:

```text
[('DuckDB','duckdb'), ('Spark','spark'), ('Azure SQL','tsql'),
 ('Oracle','oracle'), ('PostgreSQL','postgres')]
```

Transpilation reaches `executable_sql` for both engines — asserted on the transformation,
not merely that the string changed:

```text
oracle   -> duckdb   NVL(name,'x')  =>  COALESCE(name, 'x')
oracle   -> spark    NVL(name,'x')  =>  COALESCE(name, 'x')
postgres -> duckdb   id::text       =>  CAST(id AS TEXT)
postgres -> spark    id::text       =>  CAST(id AS STRING)
```

The DuckDB/Spark split on the cast (`TEXT` vs `STRING`) confirms the target dialect is
really being honoured rather than one canned conversion being applied.

## End-to-end — the test that catches "transpiles but won't run"

Both dialects execute against DuckDB through the real adapter with a real CSV:

```text
oracle    status=succeeded rows=3
          "SELECT COALESCE(name,'x') AS n, value FROM t WHERE id < 3"
          [('name_0', 15.58…), ('name_1', 94.23…)]
postgres  status=succeeded rows=3
          "SELECT CAST(id AS TEXT) AS s, name FROM t WHERE name ILIKE 'name_1%' LIMIT 3"
          [('1','name_1'), ('10','name_10')]
```

## The ROWNUM / DUAL trap is genuinely handled

This was the plan's main risk: both constructs transpile verbatim and then fail at the
engine with "column ROWNUM not found", which reads as broken Oracle support. The builder
now raises a `TranslationError` naming the construct before execution
(`services/execution_request_builder.py:13-16, 34-38`).

I checked it against false positives as well as true ones, which is the part that usually
goes wrong with regex-based detection:

| dialect | input | result |
|---|---|---|
| oracle | `... WHERE ROWNUM <= 3` | diagnosed, names `ROWNUM` |
| oracle | `SELECT SYSDATE FROM DUAL` | diagnosed, names `DUAL` |
| oracle | `SELECT NVL(a,'x') FROM t` | runs |
| postgres | `SELECT id::text FROM t` | runs |
| duckdb | `SELECT rownum_total FROM t` | **runs** — word boundary holds, not a substring match |
| postgres | `... WHERE ROWNUM < 5` | not diagnosed — correctly scoped to Oracle |

## Negative controls

All three the plan required, each failing its own tests:

| mutation | result |
|---|---|
| remove `"Oracle"` from `DIALECT_MAPPING` | 4 failed, 43 passed |
| disable the transpile branch | 6 failed, 16 passed |
| add a fake `ORACLE` member to `EngineKind` | 1 failed, 25 passed |

## Gates

```text
ruff check          All checks passed
ty check .          All checks passed   (whole repo)
pytest              392 passed, 7 deselected   (was 384; +8 tests)
git status --short  clean
```

## The boundary held

Version still `0.5.2`. No tag, no `main` change. `pyarrow` import, `timid = true`, and
the overwrite confirmation all intact.

## Deferred

No Oracle or PostgreSQL server is contacted at any point, so dialect fidelity is only as
good as sqlglot's. Constructs outside the two detected here will still fail at the engine
— a documented limitation rather than a defect. The README should state plainly that
these are source dialects, not supported backends, so nobody reads the dropdown as a
compatibility promise.

STATUS: APPROVED
