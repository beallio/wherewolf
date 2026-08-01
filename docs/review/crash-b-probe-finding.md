# Finding — crash B was the SchemaWorker teardown race

Date: 2026-08-01
Probe branch: `probe/crash-b-schema-worker` @ `518dd51`
CI run: `30706686023` (30 jobs)

## Result

**The unexplained Python 3.12 segfault ("crash B") that caused 3.12 to be deprecated was the
same defect root-caused and fixed in Phase 8: `SchemaWorker` QThreads destroyed while still
running.**

| Python 3.12, `baseline` mode, `timid = true` | native crashes |
|---|---|
| before (`ci-qt-flake-312` investigation) | **7 / 32 ≈ 22%** |
| with only the `closeEvent` schema-worker drain applied | **0 / 30** |

P(0 crashes in 30 at a 22% rate) = `0.78^30` ≈ **0.0006**. The decision rule was stated before
measuring: 0/30 confirms, ≥4/30 refutes, 1–3/30 ambiguous.

## Method — one variable

The probe branched from `70ba77e`, the last commit with `requires-python = ">=3.12"`, which
still contains the defect (its `closeEvent` saves settings and does not drain workers) and sits
on the lineage where 7/32 was measured. `QueryController` does not exist at that commit, so the
entire change was five lines:

```python
for worker in list(self._schema_workers):
    if worker.isRunning():
        worker.quit()
        worker.wait()
self._schema_workers.clear()
```

Nothing else was altered — no dependency changes, no test changes beyond one added regression
test, same `baseline` probe mode, same `timid = true`.

**Why the probe could not run on `dev`:** `dev` now uses PEP 758 unparenthesized exception
syntax (`src/wherewolf/storage/history.py:80`), which is a **SyntaxError on 3.12**. The suite
cannot import there. Any future 3.12 work faces the same wall.

## Validity checks

Because a previous matrix in this project silently ran 3.14 while claiming to test 3.12, the
run was verified rather than trusted:

- `Verify interpreter` step printed `interpreter: 3.12` — the step was added to the probe
  workflow specifically for this.
- `.github/probe-mode` = `baseline`, matching the conditions of the 7/32 measurement.
- `timid = true` present in `pyproject.toml` on the probe branch. Crash B was known to persist
  *despite* `timid`, so this is the correct comparison.
- The suite genuinely ran: **225 passed, 1 skipped** per job.
- All 30 jobs concluded `success`; there were no failures to classify.

## What this means

The three-crash picture is now two, and both are explained:

| | mechanism | status |
|---|---|---|
| **A** | coverage C tracer + Qt on 3.14 | fixed by `timid = true` |
| **B** | `SchemaWorker` QThread destroyed while running | **fixed** — same defect as Phase 8's crash |

Crash B was never 3.12-specific. It is a pure timing race, and 3.12 simply lost it far more
often (22%) than 3.14 did (6% on the Phase 8 branch, 0/75 on `dev`).

**Consequence: the Python 3.12 deprecation was a workaround for a bug that is now genuinely
fixed.** Restoring `requires-python = ">=3.12"` is a real option for 0.6.0.

## Cost of restoring 3.12 — for the maintainer to weigh

This is **not** a recommendation, and nothing should be changed without an explicit decision.
The work would be:

1. Lower `requires-python` to `>=3.12`. `ruff format` then re-parenthesizes the PEP 758
   exception syntax automatically, because it targets the declared floor — the same mechanism
   that made an earlier revert impossible to land, working in our favour this time.
2. Revert the `UP035`/`UP037` rewrites that ruff required under the 3.14 target.
3. Restore `3.12` to the `ci.yml` test matrix, keeping the `Verify interpreter` step.
4. Re-lock (`uv lock`, `uv sync --all-extras --dev`).
5. Re-measure: 3.12 should now match 3.14. A 25-run probe per leg is the minimum, and one
   clean batch of 25 proves little — state `(1-p)^N` and pick N accordingly.

Against that: `uv tool install` provisions its own interpreter, so the floor costs users
little either way, and 3.14-only syntax is already in the tree.

## Residual risk

0/30 bounds the 3.12 rate but does not prove zero; a rate below ~1-in-30 would be undetected.
The mechanism is understood and the fix is causally demonstrated (removing the drain
reproduces a SIGSEGV on demand), which is far stronger evidence than the sample size alone.

## Housekeeping

`probe/crash-b-schema-worker` is a throwaway branch kept as evidence. It can be deleted once
this finding is accepted. It cannot fire CI on `main` or `dev`: the probe workflow is absent
from `main`, and `dev`'s copy is scoped to the deleted `feat/ci-qt-flake-312` branch plus a
path filter.
