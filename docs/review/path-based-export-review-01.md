# Review — path-based-export (round 01)

Branch: `feat/path-based-export` @ `4857368`
Reviewed against: `docs/plans/2026-08-01_path-based-export.md`

## Verdict

CHANGES_REQUESTED — **the exit criterion is unguarded.** The implementation streams correctly
today; nothing stops it regressing tomorrow, and I proved that rather than inferring it.

## What you did well

- **The streaming implementation is right.** `COPY (<executable_sql>) TO '<temp>' (FORMAT ...)`
  on the request-scoped connection, wrapped in the atomic writer. That is exactly the design
  the plan asked for.
- **The atomic write is correct and genuinely tested** — temp sibling, `os.replace` only on
  success, cleanup in `finally`, with
  `test_atomic_writer_preserves_existing_bytes_and_removes_temp` asserting the original's
  **bytes** survive a failed write. V5 is satisfied.
- **`export/` and the whole Streamlit path are untouched.** The diff is empty. You wrote new
  path-based code rather than extending the byte-based `Exporter`, as required.
- **`ExportController.shutdown()` is wired into `closeEvent`** — the crash-safety pattern this
  project learned the hard way.
- **The session log says "not measured"** for the V8 mutations and the V11 crash batches
  instead of inventing results. That is the recording rule working under pressure, and it is
  why I knew exactly where to look. Keep doing this.

### My measurements

| check | result |
|---|---|
| suite on **3.14** | 346 passed, 1 skipped |
| suite on **3.12** | 346 passed, 1 skipped — identical |
| `run-quality-gates` | pass |
| **V9** 3.14-only syntax | none |
| **V2** Streamlit + `export/` diff | empty |
| **V11** crash gate (25 of 50 so far) | 0 crashes; second batch running |
| **V8 mutation 1 (materialise instead of stream)** | **DID NOT BITE — see H1** |

## Required changes

### H1. Nothing detects a regression from streaming to materialising

This is the exit criterion: *"full DuckDB CSV/Parquet export does not materialize the entire
result as a Polars DataFrame plus bytes."*

I replaced the `COPY` call with the thing the phase exists to prevent:

```python
def copy_to(path: Path) -> None:
    frame = con.sql(request.executable_sql).pl()      # materialise everything
    frame.write_csv(path) if fmt is ExportFormat.CSV else frame.write_parquet(path)
```

**The entire suite passed — 346 passed, 1 skipped.** Not one test noticed.

`tests/test_full_export.py` has two tests and both only inspect the **output file**. The plan
warned about precisely this: *"a test that only inspects the output file cannot distinguish
streaming from materialising."* The output is byte-identical either way — that is the whole
problem.

**Fix (V4 as specified):** spy on the request-scoped connection and assert **both**:

1. a `COPY ... TO` statement is issued for the full-export path; and
2. **no** materialisation call — `.pl()`, `.arrow()`, `.fetchall()`, `.df()` — occurs on it.

Keep exporting **more rows than `preview_limit`** so a preview-shaped result cannot masquerade
as a full one. Then re-apply the mutation above and confirm the new test **FAILS**. Paste the
failing node id.

### H2. Cancellation is unverified

`tests/test_export_controller.py` contains one test (emits one terminal result). Task 10 and V6
are uncovered: cancelling mid-export must leave **no partial destination file**, **no temp
file**, and an existing destination **untouched**; cancelling a finished export must be safe.

Given a half-written export is a user-visible data hazard, this needs a real test, not an
inspection. Task 9's other two Red cases are also missing — the handle published **before**
work starts, and a failure surfacing as a failed export rather than an exception.

### H3. The selection logic was duplicated, not reused

`src/wherewolf/selection.py` is a **second** implementation of visual-column-order selection.
`desktop/clipboard_serializers.py` still has its own. The plan was explicit:

> **Reuse that logic; do not write a second implementation that can drift.** … **Do not
> duplicate it** — if it needs to be shared, extract it once and have both call sites use it.

Two copies of "visual order, hidden columns excluded, discontiguous rule" will drift, and when
they do, **copy and export will silently disagree about the same selection** — the kind of bug
users report as "the export is wrong" with no error anywhere.

Extract once and route both call sites through it. `tests/test_selection.py` currently holds a
single test; whichever module survives needs the full set — moved columns, hidden columns,
discontiguous selection.

### H4. Run the V8 mutations

The log records them as not measured, which is honest. Now run them, and record the node id you
actually observed for each. Mutation 1 is H1 above; I have run it and it does not bite, so that
one is already answered — fix the test, then confirm it fails.

### H5. One commit for thirteen tasks

The plan specifies one commit per task, and the round produced two: a baseline and a single
`feat(export): add path-based desktop exports` carrying everything.

I am **not** asking you to rewrite history. Going forward in this phase, commit per task. The
granularity is what makes a failure bisectable, and it is the reason the plan is written as
discrete tasks rather than a description of the finished state.

## Delegate the low-level work to your subagents

You have seven read-only `agent-memory` subagents available
(`~/.codex/agents/*.toml`), and the MCP server is declared for this project with
`--tool-profile full`. Use them and **surface what they return to me** rather than acting on it
silently:

- **`memory_researcher`** — before you start this round, ask it for prior constraints, decisions
  and **failed approaches** relevant to export, streaming, atomic writes and Qt worker
  lifetime. Report the claim IDs of anything consequential in the session log.
- **`memory_evidence_reviewer`** — if a remembered claim would change what you build, audit it
  before relying on it, and report what is supported, contradicted or stale.

Treat memory as **historical evidence, not current truth** — its own instructions say to
revalidate drift-prone claims against the repository, which matches this project's rule that a
claim is something to verify rather than trust. Do **not** ask `memory_curator` or
`memory_lifecycle_manager` to write anything; nothing in this round authorizes a memory
mutation.

## Verification before marking complete

- The V4 streaming spy, plus the mutation re-applied and its **failing** node id.
- Cancellation tests per H2.
- Single shared selection implementation per H3, with the full test set.
- All six V8 mutations with observed node ids, `--color=no`, mutation-applied check.
- `./run.sh uv run pytest -q` on 3.14 and `--python 3.12` — record both, then restore with
  `./run.sh uv sync --all-extras --dev --python 3.14`.
- `scripts/orchestration/run-quality-gates` → exit 0.
- `git status --short` → prints nothing.
- **V11**: I am measuring 50 runs myself this round; do not re-run it unless you change
  `closeEvent` or worker lifetime.

## Constraints

Do not remove `timid = true`. Do not disable coverage. Do not skip, delete or xfail tests. Do
not modify `export/exporter.py`, `DuckDBEngine`, or any Streamlit path. Do not touch `main`. Do
not bump the package version.

## Deferred — correctly recorded by you

No human has exported from a real window; all Qt tests are offscreen. **Streaming is verified
structurally, not by a memory measurement** — no multi-gigabyte export was performed, and the
log says so, which is the right way to state it. Spark export unverified. macOS and Windows
dialogs unverified.

STATUS: CHANGES_REQUESTED
