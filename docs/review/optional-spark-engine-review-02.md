# Review — optional-spark-engine (round 02)

Branch: `feat/optional-spark-engine` @ `0474875`
Reviewed against: `docs/plans/2026-08-01_optional-spark-engine.md` and review 01

## Verdict

APPROVED.

Both review items are resolved, and the two defects this project has carried for five
consecutive plans are finally fixed — verified end-to-end, not just removed from the source.

## I1 — CI now proves both exit criteria

The regression is gone. The two legs now install differently, which is the whole point:

| leg | install | runs |
|---|---|---|
| `test` (`ci.yml:30,58,67`) | `uv sync --dev` — **no extras** | `pytest` |
| `test-spark` (`ci.yml:93,102`) | `uv sync --extra spark --dev` + Temurin | `pytest -m spark` |

`Verify interpreter` is present in both (lines 59 and 94). A DuckDB-only install is now genuinely
exercised without pyspark present, and Spark is genuinely exercised where it is installed.
Before this round CI installed Spark and tested none of it; now each leg proves a different
exit criterion.

## I2 — the long-deferred defects are fixed

**`get_schema` no longer swallows.** The `except Exception: return empty` is replaced by
`try/finally`, which lets the error propagate while still dropping views. I verified the
behaviour the plan actually required — that a failure is **distinguishable from an empty
schema** — by inspecting a nonexistent path through the real adapter:

```text
columns   : ()
error_type: AnalysisException
has_error : True
```

A genuinely empty schema returns `error_type=None`. The two cases are now separable, which they
were not in any prior phase. This defect appeared in five consecutive plans; it is closed.

**`cancelAllJobs` is gone.** `grep -rn cancelAllJobs src/` returns nothing.
`spark_engine.py:139` sets a request-scoped job group and `:185` cancels only that group, so
cancelling one request no longer tears down unrelated jobs in the same context.

## Final state — measured by review

| check | result |
|---|---|
| default tier, **3.14** | 364 passed, 7 deselected |
| default tier, **3.12** | 364 passed, 7 deselected — identical |
| **spark tier** | 7 passed, 364 deselected in 8.5s |
| `run-quality-gates` | pass |
| **V3** no JVM in default tier | proven — `getOrCreate` rigged to raise, suite still passed |
| RAM during spark tier | 2897 M → 2273 M (**624 M**, within the 512m driver + overhead) |
| **`/tmp` during spark tier** | 765 M → **763 M** |
| `cancelAllJobs` in `src/` | absent |
| `git status --short` | clean |

**The memory constraint is satisfied with room to spare.** `/tmp` moved 2 MB because
`SPARK_LOCAL_DIRS` resolves through the `/tmp/wherewolf` symlink onto `/dev/mapper` — real disk
with 6.8 G free — rather than the tmpfs that counts against RAM. That single choice is what makes
this tier safe to run on this machine.

## What this phase delivered

pyspark moved to an optional `[spark]` extra; a `spark` pytest marker with `-m "not spark"` in
`addopts` so the JVM tier is opt-out by default; a session-scoped, memory-bounded Spark fixture;
lazy session creation; graceful degradation when pyspark is absent; availability messaging;
request-scoped job groups replacing `cancelAllJobs`; schema errors that are reported rather than
swallowed; temporary view and directory cleanup; JSON vs JSON-Lines handling; and two CI legs.

The stale unconditional skip at `tests/test_duckdb_engine.py:77` — whose stated reason
("Spark requires complex setup for CI") had become false — is now a properly marked Spark test.

## Process notes

**The session log is honest where it matters.** It records all six V8 mutations with observed
failing node ids, and states *"Peak memory: not measured in this round"* rather than estimating.
That is the correct answer, and I measured it independently above so the figure now exists in
the record.

**Commit granularity slipped again.** Round 02 landed Tasks 5–13 in a single
`feat(spark): complete optional engine workflow` commit, as round 01 of Phase 12 did. The plan
asks for one commit per task and review 01 repeated it. I am not blocking on it or asking for a
history rewrite — but it is now a pattern across two phases, and it costs the bisectability the
task breakdown exists to provide. Worth carrying into Phase 14's plan as an explicit,
checked requirement rather than a stated preference.

## Deferred — state these plainly and do not overstate

**Spark is verified on Linux, with a single JDK, on one machine, with `local[1]` and tiny data.**
No performance or scale testing was done — the tier is deliberately bounded, so nothing here says
anything about Spark throughput. Cluster and remote Spark are unverified. macOS and Windows are
unverified. The CI Spark leg raises confidence for Linux only.

STATUS: APPROVED
