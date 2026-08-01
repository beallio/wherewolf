# Plan: Fix intermittent Qt crash under coverage (qt-coverage-flake)

## Context

The test suite on `dev` aborts the interpreter on roughly **20% of runs**. This is not a
test failure — it is `Fatal Python error: Aborted` (SIGABRT) or `Segmentation fault`
(SIGSEGV), exit 134 or 139. It intermittently blocks commits, because
`.git/hooks/pre-commit` runs pytest, and it will intermittently redden CI.

This plan does one thing: **find and fix the root cause.** It is deliberately small.

### What is already established — do not re-derive this

Measured on `dev` at `3314afc`:

| Condition | Crashes |
|---|---|
| `pytest -q --no-cov` (coverage OFF) | **0 / 70** |
| `pytest -q` (coverage ON, the default) | **8 / 40** |

The crash **requires coverage to be enabled**. `[tool.pytest.ini_options] addopts` in
`pyproject.toml` contains `--cov=src --cov-report=term`, so coverage is on by default and
off only when `--no-cov` is passed. This is why the crash first appeared in
`scripts/orchestration-hooks/quality-gates` rather than during development.

A representative C stack trace, captured from a real crash:

```text
Current thread's C stack trace (most recent call first):
  ...
  PyQt6/QtCore.abi3.so
  libQt6Core.so.6, at QObject::event
  libQt6Widgets.so.6, at QApplicationPrivate::notify_helper
  libQt6Core.so.6, at QCoreApplication::notifyInternal2
  libQt6Core.so.6, at QCoreApplicationPrivate::sendPostedEvents
```

with a second thread parked in `concurrent/futures/thread.py`. The fault is in Qt's
posted-event delivery, and one observed crash occurred during
`tests/test_schema_worker.py::test_schema_worker_emits_error_result_on_exception_and_still_closes_adapter`,
which drives a `QThread`.

### Two hypotheses already tested and DISPROVEN — do not repeat them

Both were plausible, both were measured, both failed. They are already committed as
`3314afc` on their own hygiene merits, and that commit says explicitly that neither fixes
the crash. **Do not revert them and do not re-attempt them.**

1. *Tests constructing top-level widgets without `qtbot.addWidget`.* Fixed in
   `tests/test_main_window.py`. Crash rate afterwards: **6 / 25**. Not the cause.
2. *`SchemaWorker` (a `QThread`) being garbage-collected while still running, because
   `result_ready` is emitted from inside `run()` before its `finally` block.* Fixed by
   waiting on the thread in `tests/test_schema_worker.py`. Crash rate afterwards:
   **8 / 40**. Not the cause.

A cautionary note on method, because it is what made both of those look right: an early
measurement of **0 crashes in 15 runs** was treated as confirmation. At a ~20% rate,
observing zero in 15 runs happens about 3.5% of the time by chance, and at the then-assumed
13% rate about 12% of the time. **A small clean sample is not evidence of a fix.** This
plan therefore specifies exact sample sizes; do not shorten them.

### The leading hypothesis

`[tool.coverage.run]` in `pyproject.toml` currently contains only `data_file`. There is
**no `concurrency` setting**, so coverage.py uses its default single-threaded tracer.
Qt starts and joins threads in C++ (`QThread`), and the suite also uses
`concurrent.futures` via the Streamlit app module. Tracing threads that a C++ library
creates and destroys is a known source of native crashes in coverage.py.

`concurrency = "thread"` is the first thing to test. It may not be the answer — treat it as
a hypothesis to measure, not a conclusion.

### Constraints

- **Do not disable coverage to make the crash go away.** Removing `--cov` from `addopts`,
  adding `--no-cov`, or deleting the coverage gate is not a fix and will be rejected.
  Coverage must remain enabled by default and must still report `src/`.
- **Do not delete, skip, or `xfail` any test** to avoid the crash. If you believe a
  specific test is genuinely at fault, say so in the session log with evidence and stop.
- **Do not touch the Streamlit path**: `src/wherewolf/app.py`, `engines.py`, `ui/`,
  `export/`, `storage/`, `constants.py`, `.streamlit/`.
- Prefer a configuration fix over a code change. If code must change, keep it minimal and
  explain why in the session log.

### Repo mechanics

- `.git/hooks/pre-commit` runs `ruff check .`, `ruff format .`, `ty check .`, `pytest`,
  then `scripts/check_tdd.sh`. **The pytest step runs with coverage, so the hook itself has
  a ~20% chance of hitting this crash and failing your commit.** If that happens, retry —
  but confirm the failure output actually contains `Fatal Python error` or
  `Segmentation fault` before assuming it is the known flake rather than a real failure.
- `scripts/check_tdd.sh` requires a flat `tests/test_<basename>.py` for every staged
  `src/**/*.py`. This plan is not expected to add any `src/` module.
- ruff is on the 0.16 default rule set.
- All commands go through `./run.sh`.
- Baseline suite result when it does not crash: **179 passed, 1 skipped**.

**Slug used throughout this plan:** `qt-coverage-flake`

---

## Orchestration Contract

**Slug:** `qt-coverage-flake`

**Plan file:**

```text
docs/plans/2026-07-31_qt-coverage-flake.md
```

**Implementation branch:**

```text
feat/qt-coverage-flake
```

**Round-complete marker:**

```text
/tmp/wherewolf/qt-coverage-flake_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/qt-coverage-flake_finalized
```

**Review notes:**

```text
docs/review/qt-coverage-flake-review-*.md
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
git checkout -b feat/qt-coverage-flake
```

Commit this plan first:

```bash
git add docs/plans/2026-07-31_qt-coverage-flake.md
git commit -m "docs(plan): add qt-coverage-flake implementation plan"
```

---

## Implementation Tasks

Six small tasks. Each is one commit. **Measure before and after every change** — this bug
has already defeated two confident fixes that were never properly measured.

Save this helper once and reuse it for every measurement in this plan:

```bash
cat > /tmp/wherewolf/flake.sh <<'EOF'
#!/usr/bin/env bash
# flake.sh <runs> [extra pytest args] -> prints "crashes: C / N"
runs="$1"; shift
cd "$(git rev-parse --show-toplevel)"
c=0
for i in $(seq 1 "$runs"); do
  if ! ./run.sh uv run pytest -q "$@" >/tmp/wherewolf/flake-last.txt 2>&1; then
    if grep -qE "Fatal Python error|Segmentation fault" /tmp/wherewolf/flake-last.txt; then
      c=$((c+1)); echo "  crash on run $i"
    else
      echo "  NON-CRASH FAILURE on run $i (a real test failure, not the flake):"
      tail -20 /tmp/wherewolf/flake-last.txt; exit 2
    fi
  fi
done
echo "crashes: $c / $runs"
EOF
chmod +x /tmp/wherewolf/flake.sh
```

It distinguishes a native crash from an ordinary test failure and exits 2 on the latter, so
a genuine regression can never be silently counted as "just the flake".

---

### Task 1 — Session log and measured baseline

Create **and commit** `docs/agent_conversations/2026-07-31_qt-coverage-flake.md` with the
`AGENTS.md` Section 14 headings. Append to it after every task.

Record the current state with your own measurements, not the Context's numbers:

```bash
/tmp/wherewolf/flake.sh 30            # coverage ON  (expect roughly 4-8 crashes)
/tmp/wherewolf/flake.sh 30 --no-cov   # coverage OFF (expect 0)
```

Paste both results verbatim. If coverage-off is **not** 0/30, stop and report — the
premise of this plan is wrong and the rest of it does not apply.

Commit: `docs: record qt coverage flake baseline`.

---

### Task 2 — Test the `concurrency` hypothesis

Add to `[tool.coverage.run]` in `pyproject.toml`:

```toml
concurrency = ["thread"]
```

Measure:

```bash
/tmp/wherewolf/flake.sh 40
```

**Decision rule, stated in advance so the result cannot be rationalised afterwards:**

- **0 / 40** — accept as the fix and go to Task 5. (At a 20% rate, seeing zero in 40 runs
  by luck has probability 0.8^40 ≈ 0.00013.)
- **1-2 / 40** — reduced but not fixed. Record it, keep the setting, continue to Task 3.
- **3+ / 40** — no meaningful effect. Record it, **revert the setting**, continue to Task 3.

Record the exact count either way. Commit only if you keep the setting:
`fix(coverage): trace threads under the thread concurrency model`.

---

### Task 3 — Only if Task 2 did not reach 0/40: identify the crashing test

Do not guess. Get the data:

```bash
for i in $(seq 1 40); do
  out=$(./run.sh uv run pytest -v 2>&1) || {
    echo "### crash $i, last completed test:"
    printf '%s\n' "$out" | grep -E "PASSED|FAILED" | tail -1
    printf '%s\n' "$out" | grep -A25 "Current thread's C stack" | head -30
  }
done
```

Collect **at least 4 crash samples** and record every one in the session log. Then answer,
with evidence:

1. Is the last-completed test the same one every time, or does it vary?
2. Does the C stack always show Qt posted-event delivery, or do the traces differ?
3. Do the crashes cluster around tests that start a `QThread` (`tests/test_schema_worker.py`)
   or around widget-heavy tests?

If a single test is consistently implicated, run that file alone in a loop under coverage
(`/tmp/wherewolf/flake.sh 40 tests/<file>.py`) and see whether it crashes in isolation. A
crash in isolation points at that test; a crash only in the full suite points at
interaction or teardown ordering.

Commit: `docs: record qt coverage flake crash samples` (session log only).

---

### Task 4 — Only if still unfixed: test the next hypothesis, one at a time

Try these **in order, measuring 40 runs after each, keeping only what helps**. One change
per measurement — never two at once, or you cannot attribute the result.

1. `sigterm = true` under `[tool.coverage.run]`.
2. `[tool.coverage.run] omit` for the Qt worker module
   (`src/wherewolf/desktop/workers/*`), which stops coverage tracing the code that runs on
   the `QThread`. Note in the session log that this trades a little coverage for stability.
3. Set `PYTHONFAULTHANDLER=1` and capture a fuller trace to pin the exact Qt object being
   delivered to; record findings even if they do not yield a fix.

Stop at the first option that reaches **0/40** and record the ones that did not work — a
disproven hypothesis is a useful result and belongs in the log.

If none reach 0/40, **stop and report** rather than inventing a workaround. Write up in the
session log exactly what was tried, each measured rate, and the best current theory. An
honest dead end is an acceptable outcome for this plan; a coverage-disabling hack is not.

Commit: `fix(coverage): <specific change>` for whichever worked.

---

### Task 5 — Add a regression guard

Add `scripts/check_flake.sh`, executable, that runs the suite N times (default 20, first
argument overrides) under coverage and exits non-zero if any run produces
`Fatal Python error` or `Segmentation fault`. It must distinguish a native crash from an
ordinary test failure and report which it saw.

Do **not** wire it into `pre-commit` or `quality-gates` — 20 suite runs per commit is too
slow. It is an on-demand tool. Document it in the session log and in `README.md` under
Development, in one or two sentences.

Commit: `test: add repeated-run guard for the Qt coverage crash`.

---

### Task 6 — Close out the session log

Record: every hypothesis with its measured crash rate (including the two already disproven
in the Context), the fix that worked and why, the final measurement, and anything still
unexplained. If the root cause is understood but only mitigated, say so plainly.

Commit: `docs: close out qt coverage flake session log`.

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

This bug has already survived two confident fixes that were never measured properly. The
verification below is therefore mostly about **sample size**. Do not shorten the runs.

### V1 — The crash is gone under coverage

```bash
/tmp/wherewolf/flake.sh 40
```

**Pass condition: `crashes: 0 / 40`.**

**Failure looks like:** any non-zero count, or the helper exiting 2 (which means a real
test failure, not the flake — investigate that separately and do not count it as noise).

Why 40: the pre-fix rate is ~20%, so a genuine fix showing zero across 40 runs has a
false-pass probability of 0.8^40 ≈ 0.00013. At 15 runs it would be ~3.5%, which is how the
first wrong fix passed for a false conclusion.

### V2 — Coverage is still actually enabled and reporting

The crash must be fixed, not sidestepped.

```bash
grep -n "addopts" pyproject.toml
./run.sh uv run pytest -q 2>&1 | tail -25
```

**Expected:** `addopts` still contains `--cov=src --cov-report=term`, and the run prints a
coverage table including `src/wherewolf/desktop/`, `src/wherewolf/services/` and
`src/wherewolf/domain/` with a TOTAL line.

**Failure looks like:** `--cov` removed or `--no-cov` added anywhere; no coverage table;
or a TOTAL materially below the current ~84%. If `omit` was used in Task 4, the omitted
module may legitimately disappear — call that out explicitly rather than letting it pass
unremarked.

### V3 — No test was removed, skipped, or xfailed to dodge the crash

```bash
./run.sh uv run pytest -q --no-cov 2>&1 | tail -2
git diff dev..HEAD -- tests/ | grep -E "^\-.*def test_|^\+.*@pytest.mark.(skip|xfail)" || echo "OK: no tests deleted or newly skipped"
```

**Expected:** still `179 passed, 1 skipped`, and the grep prints the OK line. The one
pre-existing skip is in `tests/test_duckdb_engine.py` and is unrelated.

**Failure looks like:** a lower passed count, a deleted `def test_`, or a newly added
`skip`/`xfail`.

### V4 — The guard script actually detects a crash

A guard that cannot fail is worthless. Prove it catches one before trusting it.

```bash
scripts/check_flake.sh 5        # expect: passes, exit 0
```

Then temporarily make a test abort the interpreter — for example add
`import os; os._exit(139)` inside a single test — and run the guard again:

```bash
scripts/check_flake.sh 3        # expect: FAILS, non-zero exit, reports a crash
```

**Failure looks like:** the guard passing against a deliberately crashing suite, or
reporting it as an ordinary test failure. Revert the sabotage afterwards and confirm
`git status --short` is clean.

### V5 — Negative control (runs last)

```bash
set -o pipefail
cd "$(git rev-parse --show-toplevel)"
git status --short
./run.sh uv run ruff check .
./run.sh uv run ruff format --check .
./run.sh uv run ty check src/
/tmp/wherewolf/flake.sh 40
scripts/orchestration/check-review-notes-not-deleted
```

`git status --short` must print nothing. This passes only if the fix is present *and*
effective: V4 has just shown the guard detects a real crash, so a clean 40-run sweep here
is not something an empty change could produce.

### Deferred and explicitly NOT verified

- **CI is unproven.** The fix is measured only on this Linux machine with this exact
  PyQt6/Qt/coverage build. GitHub runners may behave differently; nothing has been pushed.
- **macOS and Windows are entirely unverified**, as with every phase so far.
- **The 40-run sweep bounds the rate, it does not prove zero.** A residual crash rate below
  roughly 1 in 40 would not be detected. If you have reason to think the fix is a
  mitigation rather than a cure, say so plainly in the session log.
- **State whether the root cause is understood or merely mitigated.** If the fix works but
  you cannot explain *why*, that is an acceptable outcome — but it must be recorded as
  such, not written up as a diagnosis.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished qt-coverage-flake
```

This writes:

```text
/tmp/wherewolf/qt-coverage-flake_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer qt-coverage-flake`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/qt-coverage-flake-review-*.md
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
   scripts/orchestration/clear-finished qt-coverage-flake
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
   git add docs/review/qt-coverage-flake-review-*.md
   git commit -m "docs(review): record qt-coverage-flake review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished qt-coverage-flake
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer qt-coverage-flake` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed qt-coverage-flake
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize qt-coverage-flake
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/qt-coverage-flake_finalized
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
scripts/orchestration/finalize qt-coverage-flake
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/qt-coverage-flake_finished
/tmp/wherewolf/qt-coverage-flake_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
