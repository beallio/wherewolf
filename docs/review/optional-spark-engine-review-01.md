# Review — optional-spark-engine (round 01)

Branch: `feat/optional-spark-engine` @ `8884956`
Reviewed against: `docs/plans/2026-08-01_optional-spark-engine.md`

## Verdict

CHANGES_REQUESTED — **Tasks 1–4 are done and done well; Tasks 5–13 remain.** One consequence of
stopping here needs attention before it ships: CI currently installs Spark and tests none of it.

## What you did well — the memory-safety work is exactly right

The hard constraint of this phase was not exhausting a machine with ~2.9 GB RAM and a `/tmp`
tmpfs holding 765 MB. You met it, and I verified it with measurements rather than reading:

**The default tier starts no JVM.** I rigged `SparkSession.Builder.getOrCreate` to raise and ran
the full default suite:

```text
353 passed, 5 deselected in 6.51s
```

Nothing constructed a session. That is V3 proven by counterfactual, not inferred from runtime.

**The Spark tier stays inside its budget.** Measured across `pytest -m spark`:

| | before | after |
|---|---|---|
| RAM available | 2911 M | 2373 M |
| `/tmp` free | 765 M | **763 M** |
| spill written to `spark-local` | — | 0 |

538 MB for the JVM, within the 512m driver budget, and **`/tmp` moved 2 MB**. The reason is
right: `SPARK_LOCAL_DIRS = /tmp/wherewolf/spark-local` resolves through the symlink to
`/home/beallio/.local/state/wherewolf-cache/spark-local` on `/dev/mapper` — real disk with 6.8 G
free, not the tmpfs that counts against RAM. That single choice is what makes this tier safe to
run here.

The fixture matches the specification exactly — session-scoped, `local[1]`,
`spark.driver.memory=512m`, `spark.ui.enabled=false`, `spark.sql.shuffle.partitions=1`, and a
clean skip when pyspark is absent. Spark tier: **5 passed, 353 deselected in 7.39s**.

Also done: pyspark moved to `[project.optional-dependencies] spark`, the `spark` marker
registered with `-m "not spark"` in `addopts`, and the stale unconditional skip at
`tests/test_duckdb_engine.py:77` resolved — it is now a properly Spark-marked test rather than a
skip whose stated reason had become false.

## Required changes

### I1. CI now installs Spark and tests none of it

This is the one item that must not ship as-is, and it is a **net loss** against `dev`.

Both CI legs run `./run.sh uv sync --all-extras --dev` (`ci.yml:30` and `ci.yml:63`), and
`--all-extras` now includes the new `spark` extra. Meanwhile `addopts` carries `-m "not spark"`.
So CI:

- installs pyspark **and** a Temurin JDK on every run, and
- deselects every Spark test.

Before this branch, CI exercised three real `SparkSession` tests. After it, CI exercises zero
while still paying the full install cost. Neither exit criterion is proven: not
*"DuckDB-only installation has no Spark import requirement"* (pyspark is installed), and not
*"Spark works when installed"* (nothing runs).

**Task 12 fixes this and should come early rather than last.** Two legs:

- one **without** the extra — `uv sync --dev` without `--all-extras`, or an explicit extra list
  excluding `spark` — proving a DuckDB-only install never imports Spark;
- one **with** the extra and Java, running `-m spark`.

Keep the `Verify interpreter` step in both. If `--all-extras` is load-bearing for other extras,
enumerate them explicitly rather than dropping the flag wholesale — and say which you chose.

### I2. Tasks 5–13 are outstanding

Specifically, with the two long-deferred defects called out:

- **Task 7 — `get_schema` still swallows the exception.** `spark_engine.py:92-94` is unchanged
  and now carries a `# KNOWN DEFECT` comment. A comment is not a resolution. The plan said this
  is fixed here **or** formally recorded as won't-fix with a reason — this is the fifth plan it
  has appeared in. Pick one and act on it.
- **Task 8 — `cancelAllJobs` is still present.** Cancellation still tears down every job in the
  context. Replace with a request-scoped `setJobGroup`/`cancelJobGroup`, and prove it by
  cancelling one of **two** concurrent requests and asserting the other completes.
- Tasks 5, 6, 9, 10, 11, 13 remain as written.

## Verification before marking complete

- All six V8 mutations with the node id **you observed**. Mutation 5 (removing `-m "not spark"`)
  is the memory-safety guard — confirm it makes V3 fail.
- `grep -rn cancelAllJobs src/` → no results.
- Schema error and genuinely-empty schema asserted **separately**.
- `./run.sh uv run pytest -q` on 3.14 and `--python 3.12`, then restore with
  `./run.sh uv sync --all-extras --dev --python 3.14`.
- `./run.sh uv run pytest -q -m spark` → record the tally **and the memory you observed**. I
  measured 538 MB and `/tmp` unchanged; report your own numbers, or "not measured".
- `scripts/orchestration/run-quality-gates` → exit 0; `git status --short` → empty.

**Already measured by review — do not re-run:** V3 (no JVM in the default tier) and the Spark
tier memory figures above.

## Delegate the low-level work

Continue using the read-only `agent-memory` subagents and **surface what they return**. Before
Task 8, `memory_researcher` on prior cancellation decisions is worth one call — this project has
a documented history with cancellation semantics (`CancellationHandle`, request-scoped DuckDB
interrupts) that the Spark path should mirror rather than reinvent. Do not invoke
`memory_curator` or `memory_lifecycle_manager`; nothing here authorizes a memory write.

## Constraints

Do not remove `timid = true`. Do not disable coverage. Do not skip, delete or xfail tests except
via the documented `spark` marker. Do not modify the Streamlit path or `DuckDBEngine`. Do not let
a Spark test run outside the memory-bounded fixture. Do not touch `main`. Do not bump the
package version.

## Deferred — state these plainly

Spark is verified on Linux with a single JDK on one machine. No performance or scale testing —
the tier uses tiny data under a hard memory budget deliberately. Cluster and remote Spark
unverified; `local[1]` only. macOS and Windows unverified.

STATUS: CHANGES_REQUESTED
