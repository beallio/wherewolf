# Phase 13 — Optional Spark engine

Slug: `optional-spark-engine`
Base branch: `dev`
Target release: 0.6.0 (minor). **Do not bump the version in this phase.**

## Context

Spark is currently a **required** dependency (`pyproject.toml:17`, `"pyspark>=4.1.2"`), so every
desktop user installs a JVM-backed engine they may never use. This phase makes it optional
without losing it.

Goal, from the migration document: **a DuckDB-only installation has no Spark import or runtime
requirement; Spark works when installed.**

Those are two different environments, and both must be proven.

### Correcting the record before you start

CI **already** runs real Spark today — this is not a greenfield addition:

- `.github/workflows/ci.yml:57-61` installs Temurin 21 via `actions/setup-java@v4`.
- Line 71 runs `pytest` unfiltered.
- Three tests start a real `SparkSession`: `tests/test_spark_engine.py:15`,
  `tests/test_multi_dataset.py:34`, `tests/test_excel_support.py:26`.
- `tests/test_duckdb_engine.py:77` is skipped unconditionally with the reason
  *"Spark requires complex setup for CI"* — **that reason is stale**, since CI has the setup.
  Resolve it: either enable the test under the Spark tier or delete it with a stated reason.
  Do not leave a skip whose justification is false.

### Memory limits — a hard constraint, not advice

This machine has **~2.9 GB available RAM**, and `/tmp` is a **3.0 GB tmpfs with ~765 MB free**.
Spark's default `SPARK_LOCAL_DIRS` is `/tmp`. An unconstrained local Spark job can fill that
tmpfs — which is RAM — and destabilise the whole machine.

Every JVM-backed test **must** run under a session fixture that sets, at minimum:

```python
SPARK_LOCAL_DIRS -> a path under /tmp/wherewolf (the cache symlink), NOT bare /tmp
spark.driver.memory        -> small and explicit (e.g. "512m")
spark.master               -> "local[1]"          # not local[*]
spark.ui.enabled           -> "false"
spark.sql.shuffle.partitions -> small (e.g. "1"); the default of 200 is pure waste here
```

**Create one session for the whole test session and reuse it** — JVM startup dominates, and
repeated sessions leak memory. Stop it explicitly at teardown. Test data must be tiny; this
tier proves *correctness of the integration*, not performance.

If you cannot make the JVM tier fit these limits, **say so and stop** rather than shipping a
suite that can exhaust the machine.

### Test tiers — the shape of this phase

| tier | needs | runs where |
|---|---|---|
| **default** | no pyspark at all | everywhere, always |
| **spark** | `[spark]` extra + Java | opt-in locally; a dedicated CI leg |

Mark JVM tests `@pytest.mark.spark` and put `-m "not spark"` in `addopts`, so the JVM tier is
**opt-out by default** locally — memory safety by construction. Opt in with an explicit
`-m spark`. CI's Spark leg opts in deliberately.

**Both CI legs are required**, because they prove different exit criteria:

- a leg installed **without** the extra proves a DuckDB-only install never imports Spark;
- a leg installed **with** the extra and Java proves Spark still works.

Java is already in CI and working, so keeping the second leg costs a step already being paid.

### What already exists — use it, do not rebuild it

- **`execution/spark_engine.py`** — the engine. Two known defects, both **in scope now**:
  - **line 94-95**: `except Exception` in `get_schema` returning an empty schema. A failure is
    indistinguishable from a table with no columns. **Four consecutive plans have deferred
    this.** It is fixed here or formally recorded as won't-fix with a reason — not deferred a
    fifth time while calling Spark done.
  - **line 158**: `sc.cancelAllJobs()` cancels **every** job in the context, including
    unrelated ones. The migration document requires a request-specific **job group** and
    `cancelJobGroup`.
- **`execution/registry.py`** — Spark detection is already lazy via `importlib.util.find_spec`,
  and `_SparkAdapter` already exists. Extend that; do not add a parallel discovery path.
- **`execution/duckdb_engine.py`** and the DuckDB adapter — untouched.
- **`domain/enums.py`** — `EngineKind` already has Spark. Reuse.
- **`tests/test_spark_engine_logic.py`, `tests/test_spark_engine_optimization.py`** — four
  existing mock-only tests that start no JVM. They belong in the **default** tier. Keep them.

### Known defects you must NOT fix here

- Streamlit's Spark usage — Phase 14 deletes it.
- Anything in the DuckDB path.

### Hard constraint: Streamlit must keep working

Do not modify `src/wherewolf/app.py`, `engines.py`, `ui/`, `export/`, `storage/`,
`constants.py` or `.streamlit/`. **Note the tension:** Streamlit imports Spark today. If making
pyspark optional would break a Streamlit import, the Streamlit path must degrade the same way
the desktop path does — but you may not restructure `app.py` to achieve it. If that proves
impossible without touching `app.py`, **stop and report** rather than forcing it.

### Python floor: 3.12 AND 3.14

CI tests both. No PEP 758 unparenthesized `except`. Let `ruff` enforce the floor.
`./run.sh uv run --python 3.12 ...` re-syncs the shared venv — restore with
`./run.sh uv sync --all-extras --dev --python 3.14` afterwards.

### The crash history you must respect

`timid = true` is load-bearing on 3.14 — do not remove it. This phase adds no new Qt worker, so
V10 is required only if you touch `closeEvent` or worker lifetime.

### Repo mechanics

- `scripts/check_tdd.sh` requires a **flat** `tests/test_<basename>.py` per staged
  `src/**/*.py`.
- The pre-commit hook runs the gates and does `git add -u`. Stage deliberately.
- Commit messages must NOT contain `Co-Authored-By:` or `Claude-Session:` trailers.
- **One commit per task.**

### Delegate low-level work to your subagents

Seven read-only `agent-memory` subagents are available (`~/.codex/agents/*.toml`) with the MCP
server on `--tool-profile full`. **Surface what they return to me; do not act on it silently.**

- **`memory_researcher`** — before Task 1, ask for prior constraints, decisions and **failed
  approaches** around Spark, optional extras, JVM startup and cancellation. Report consequential
  claim IDs in the session log.
- **`memory_evidence_reviewer`** — if a remembered claim would change what you build, audit it
  first and report what is supported, contradicted or stale.

Treat memory as **historical evidence, not current truth** — revalidate against the repository.
Do **not** invoke `memory_curator` or `memory_lifecycle_manager`; nothing here authorizes a
memory write.

### Recording rule

**"Not measured" is a complete and acceptable answer.** Record measured values, never adjectives
like "all green". After any change you report, run the command that would fail if it had not
landed and paste that output.

### Baseline

`dev` @ `a4e61d2`: **352 passed, 1 skipped** on both 3.12 and 3.14; CI green on `lint`,
`test (3.12)`, `test (3.14)`. Record your own baseline in Task 1.

## Orchestration Contract

**Slug:** `optional-spark-engine`

**Plan file:**

```text
docs/plans/2026-08-01_optional-spark-engine.md
```

**Implementation branch:**

```text
feat/optional-spark-engine
```

**Round-complete marker:**

```text
/tmp/wherewolf/optional-spark-engine_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/optional-spark-engine_finalized
```

**Review notes:**

```text
docs/review/optional-spark-engine-review-*.md
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

## Setup

Start from `dev`:

```bash
git checkout dev
git pull --ff-only origin dev
git checkout -b feat/optional-spark-engine
```

Commit this plan first:

```bash
git add docs/plans/2026-08-01_optional-spark-engine.md
git commit -m "docs(plan): add optional-spark-engine implementation plan"
```

---

## Implementation Tasks

Each task is one commit, Red before Green.

### Task 1 — Session log and baseline
Create `docs/agent_conversations/2026-08-01_optional-spark-engine.md` with the baseline commit
and measured tallies on **both** interpreters. No source changes.
Commit: `docs: record optional spark baseline`.

### Task 2 — Spark test marker and memory-safe session fixture
**Red** (`tests/conftest.py`): a `spark` marker is registered; `addopts` carries
`-m "not spark"`; a session-scoped fixture yields a configured `SparkSession` and is skipped
cleanly when the extra or Java is absent.
**Green**: implement the fixture with **every** setting from the memory-limits section above.
State the chosen values and why in the session log.
Commit: `test(spark): add opt-in marker and memory-bounded session fixture`.

### Task 3 — Move pyspark to an optional extra
**Red**: a test asserting Spark availability is discovered via `importlib.util.find_spec` and
never by a module-level `import pyspark`.
**Green**: move `pyspark` from `dependencies` to `[project.optional-dependencies] spark`.
Re-lock. Move the four existing mock-only Spark tests into the default tier explicitly.
Commit: `build: make pyspark an optional extra`.

### Task 4 — Import and launch without PySpark
**Red**: with Spark import forced to fail, the application imports, `MainWindow` constructs, and
the engine registry reports Spark unavailable — **no traceback, no crash**. Simulate absence by
patching the spec lookup, not by uninstalling.
**Green**: remove any remaining eager import.
Commit: `feat(execution): support running without pyspark installed`.

### Task 5 — Engine selector reports unavailability cleanly
**Red**: the UI shows Spark as unavailable with an actionable message naming the extra to
install; selecting it is not possible; no exception.
**Green**: availability messaging.
Commit: `feat(desktop): report spark availability in the engine selector`.

### Task 6 — Lazy session manager
**Red**: constructing the adapter starts **no** JVM; the session is created on first execution
and **reused** across requests; a Java/Spark startup failure produces an **actionable** message
naming the likely cause, not a raw stack trace.
**Green**: lazy session manager.
Commit: `feat(execution): create spark sessions lazily`.

### Task 7 — Fix `get_schema`'s swallowed exception
**Red**: a schema failure returns a `SchemaResult` carrying `error_type`/`error_message` and is
**distinguishable from a table with genuinely no columns** — assert both cases separately.
**Green**: fix `spark_engine.py:94-95`. If you conclude it must stay as-is, record that decision
and its reason explicitly instead.
Commit: `fix(spark): report schema errors instead of returning an empty schema`.

### Task 8 — Request-specific job group and cancellation
**Red**: each request sets a **job group** derived from its request id; cancelling calls
`cancelJobGroup` for **that** group; a second concurrent request is **not** cancelled — build
two and assert only one dies. `cancelAllJobs` must no longer appear in the source.
**Green**: replace `spark_engine.py:158`.
Commit: `fix(spark): cancel only the requesting job group`.

### Task 9 — Temporary view and directory cleanup
**Red**: temporary views are dropped after a request, including on error and cancellation; Spark
export temp directories are removed. Assert absence, not just success.
**Green**: cleanup in `finally`.
Commit: `fix(spark): clean up temporary views and export directories`.

### Task 10 — JSON vs JSON Lines
**Red**: a JSON-Lines file and a JSON-array file each load with the correct row count; the wrong
mode produces a clear error rather than silently wrong rows.
**Green**: handle both per a stated rule.
Commit: `fix(spark): distinguish json and json-lines inputs`.

### Task 11 — Preview result conversion
**Red** (marked `spark`): a real Spark query returns a `QueryResult` whose frame has the
expected rows, columns and order, with `preview_limit` respected and truncation reported.
Use a **tiny** dataset.
**Green**: conversion path.
Commit: `feat(spark): convert spark previews to query results`.

### Task 12 — CI: two legs
**Red/Green**: `.github/workflows/ci.yml` gains a leg installed **without** the `spark` extra
(proving a DuckDB-only install never imports Spark) and keeps a leg **with** the extra and Java
that runs `-m spark`. Keep the `Verify interpreter` step in both. Resolve the stale
unconditional skip at `tests/test_duckdb_engine.py:77`.
Commit: `ci: test with and without the spark extra`.

### Task 13 — README and close out
Document the extra (`pip install wherewolf[spark]`), the Java requirement, and how to run the
Spark tier locally. **State plainly that Spark integration is verified on Linux with one JDK
only.** Bump the README `cacheBuster` per AGENTS.md §13. Finalise the session log with measured
results.
Commit: `docs: document the optional spark extra`.

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

State decision rules **before** measuring. Record measured outcomes.

### V1 — Suite and gates, BOTH interpreters, default tier
```bash
./run.sh uv run pytest -q                         # 3.14 — no JVM should start
scripts/orchestration/run-quality-gates
./run.sh uv run --python 3.12 pytest -q --no-cov  # 3.12
./run.sh uv sync --all-extras --dev --python 3.14 # restore
```

### V2 — Streamlit path untouched
```bash
git diff dev..HEAD -- src/wherewolf/app.py src/wherewolf/engines.py src/wherewolf/ui/ \
  src/wherewolf/export/ src/wherewolf/storage/ src/wherewolf/constants.py .streamlit/
```
Must be empty. If making Spark optional breaks a Streamlit import, **stop and report**.

### V3 — No JVM in the default tier (exit criterion)
Prove it, do not assume: assert no `SparkSession` is constructed during a default run —
e.g. patch `SparkSession.getOrCreate` to fail loudly and confirm the default suite still passes.
**Failure looks like:** relying on runtime as a proxy for "no JVM started".

### V4 — DuckDB-only install has no Spark requirement (exit criterion)
With the spec lookup patched to report Spark absent, the app imports, `MainWindow` constructs,
and the registry reports unavailable. **Failure looks like:** testing only that a message
appears, without proving import succeeds.

### V5 — Spark works when installed (exit criterion)
```bash
./run.sh uv run pytest -q -m spark
```
Record the tally **and the peak memory you observed**. If you cannot measure memory, say
"not measured" — do not estimate.

### V6 — Cancellation is request-specific
Two concurrent Spark requests; cancel one; assert the other completes. `grep` must show
`cancelAllJobs` is gone from `src/`.

### V7 — Schema errors are distinguishable from empty schemas
Assert the error case and the genuinely-empty case **separately**.

### V8 — Mutation checks: prove the new tests bite
**Commit first.** Confirm each applied (`git diff --quiet` false); `--color=no`; revert between;
`git status --short` clean. **Record the node id you observed.**

1. Restore an eager module-level `import pyspark` → the no-pyspark test must FAIL.
2. Revert to `cancelAllJobs` → the request-specific cancellation test must FAIL.
3. Swallow the schema exception again → the schema-error test must FAIL.
4. Skip temporary-view cleanup → that test must FAIL.
5. Remove `-m "not spark"` from `addopts` → the default tier starts a JVM; V3 must FAIL.
6. Treat JSON-Lines as a JSON array → the row-count test must FAIL.

Mutation 5 is the memory-safety guard — it is the one that protects this machine.

### V9 — No 3.14-only syntax
```bash
grep -rn "except [A-Za-z_.]*, [A-Za-z_.]*:" src/ tests/ || echo "OK: none"
```

### V10 — Crash gate
Required **only** if you touch `closeEvent` or worker lifetime. If you do:
`scripts/check_flake.sh 25` twice, 0 crashes in 50, per-run logs preserved.

### Deferred and explicitly NOT verified
- **Spark is verified on Linux with a single JDK on one machine.** Say so. Other JDK versions,
  macOS and Windows are unverified.
- **No performance or scale testing.** The JVM tier uses tiny data deliberately, under a hard
  memory budget. Do not imply Spark throughput was measured.
- Cluster/remote Spark unverified — `local[1]` only.
- Phase 14 removes Streamlit; Phase 15 is CI/docs/release.

## Constraints

Do not remove `timid = true`. Do not disable coverage. Do not skip, delete or xfail tests
**except** by the documented `spark` marker. Do not modify the Streamlit path or `DuckDBEngine`.
Do not let a Spark test run without the memory-bounded fixture. Do not touch `main`. Do not bump
the package version.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished optional-spark-engine
```

This writes:

```text
/tmp/wherewolf/optional-spark-engine_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer optional-spark-engine`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/optional-spark-engine-review-*.md
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
   scripts/orchestration/clear-finished optional-spark-engine
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
   git add docs/review/optional-spark-engine-review-*.md
   git commit -m "docs(review): record optional-spark-engine review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished optional-spark-engine
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer optional-spark-engine` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed optional-spark-engine
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize optional-spark-engine
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/optional-spark-engine_finalized
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
scripts/orchestration/finalize optional-spark-engine
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/optional-spark-engine_finished
/tmp/wherewolf/optional-spark-engine_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
