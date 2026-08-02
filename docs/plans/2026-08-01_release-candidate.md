# Phase 15 — CI, documentation, and release candidate

Slug: `release-candidate`
Base branch: `dev`

## Context

Phases 8–14 built the desktop application and removed Streamlit. This phase validates that it
**distributes** correctly and documents it honestly.

Goal, from the migration document: **clean wheel installation works; documentation matches the
actual UI; the manual acceptance matrix is signed off; the release artifact contains required
license notices.**

### What this phase does NOT do — hard boundary

Three things are the **maintainer's** decision and are explicitly out of scope. Do not do them,
do not prepare a commit that does them, do not ask to do them:

- **Do not bump the version.** The target is **0.6.0** (a minor bump — *not* 1.0.0, despite the
  migration document's wording). The bump belongs to the maintainer at release time.
- **Do not promote `dev` to `main`.** Do not merge, tag, or push a tag.
- **Do not sign off the manual acceptance matrix.** You cannot; it requires a human at a real
  desktop on real platforms.

This phase produces a **release candidate ready for a human gate**, not a release. If any task
seems to require crossing one of these lines, stop and report.

### The manual acceptance matrix is a deliverable, not a checkbox

Section 22.5 is explicit that automated tests cannot prove native-dialog appearance, file-manager
drag/drop, platform clipboard integration, or shortcut conventions. Phase 14 accumulated a list
of `MANUAL` parity items that **no human has yet verified**:

- no browser tab or local web server starts on launch;
- the native multi-file dialog appears where supported;
- real-window geometry, dock and splitter restoration;
- clipboard behaviour against a real desktop clipboard;
- UI responsiveness during a long query;
- Spark full export;
- macOS and Windows behaviour;
- legal-notice accuracy and license files in the built artifacts.

**Task 10 turns these into a checklist a human can actually execute** — one line per item, with
the exact steps and the expected result. Vague items ("check it works") are useless; write what
to click and what should happen.

### What already exists

- CI has five green legs: `lint`, `test-duckdb (3.12/3.14)`, `test-spark (3.12/3.14)`.
  Sections 23.1's "core/unit" and "Spark integration" jobs are therefore **done**.
  **Missing: the cross-platform Qt smoke job and the build job.**
- Section 23.1 suggests Python 3.11/3.12. That is **stale** — the floor is 3.12 and CI tests
  3.12 and 3.14. Keep the current matrix; do not downgrade to match a stale document.
- `./run.sh` is a POSIX shell wrapper. Section 23.2 warns it is shell-specific and must be
  adapted deliberately for Windows. **On Windows runners, do not invoke `./run.sh`** — call
  `uv` directly and set the cache environment variables the wrapper would have set, or the job
  will fail in a way that looks like a Qt problem but is not.
- `docs/review/streamlit-parity-audit.md` lists every criterion with `MANUAL` rows — that is the
  source for Task 10.

### Local gates are not CI — the recurring failure of this migration

Three CI failures this session were all approved on green local gates:

1. `lint` broke when pyspark became optional — that leg installs without the extra; local had it.
2. Every leg broke on `uv sync --locked` — the maintainer's global
   `exclude-newer = "7 days"` stamps a relative `exclude-newer-span` into `uv.lock` that CI
   cannot reproduce. `--locked` was removed for this reason; **do not reintroduce it.**
3. A test pinning literal CI command strings then blocked the fix.

`run-quality-gates` syncs `--all-extras --dev` with everything installed. **Every CI leg installs
differently.** This phase adds two more jobs, so the exposure grows. Task 5 makes this a test.

**Assert properties, not literal command text.** A test that greps for an exact flag string
breaks on any legitimate change; assert *which leg installs which extra* and *which runs which
marker*.

### Known constraints

- Python floor 3.12 and 3.14 both tested. No PEP 758 unparenthesized `except`.
- `timid = true` stays — load-bearing on 3.14.
- `./run.sh uv run --python 3.12 ...` re-syncs the shared venv; restore with
  `./run.sh uv sync --all-extras --dev --python 3.14`.
- Memory: this machine has ~2.9 GB RAM and `/tmp` is a tmpfs with ~765 MB free. The Spark tier is
  bounded by a session fixture — do not run Spark work outside it.
- `scripts/check_tdd.sh` requires a flat `tests/test_<basename>.py` per staged `src/**/*.py`.
- No `Co-Authored-By:` or `Claude-Session:` trailers. **One commit per task.**

### Delegate low-level work to your subagents

Seven read-only `agent-memory` subagents (`~/.codex/agents/*.toml`), MCP on `--tool-profile full`.
**Surface what they return; do not act silently.** Use `memory_researcher` before Task 6 for
prior documentation decisions and deferred items — the README has accumulated claims across
seven phases and some may now be stale. Do **not** invoke `memory_curator` or
`memory_lifecycle_manager`; nothing here authorizes a memory write.

### Recording rule

**"Not measured" is a complete and acceptable answer**, as are `MANUAL` and `PARTIAL`. Record
measured values, never adjectives. After any claim you report, run the command that would fail if
it were untrue and paste that output.

### Baseline

`dev` @ `a6a9045`: **351 passed, 7 deselected** on both interpreters; Spark tier 7 passed; CI
green on all five legs. Record your own baseline in Task 1.

## Orchestration Contract

**Slug:** `release-candidate`

**Plan file:**

```text
docs/plans/2026-08-01_release-candidate.md
```

**Implementation branch:**

```text
feat/release-candidate
```

**Round-complete marker:**

```text
/tmp/wherewolf/release-candidate_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/release-candidate_finalized
```

**Review notes:**

```text
docs/review/release-candidate-review-*.md
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
git checkout -b feat/release-candidate
```

Commit this plan first:

```bash
git add docs/plans/2026-08-01_release-candidate.md
git commit -m "docs(plan): add release-candidate implementation plan"
```

---

## Implementation Tasks

One commit per task.

### Task 1 — Session log and baseline
`docs/agent_conversations/2026-08-01_release-candidate.md` with the baseline commit and measured
tallies on both interpreters and both tiers. No source changes.
Commit: `docs: record release candidate baseline`.

### Task 2 — Build wheel and sdist, inspect contents
**Red** (`tests/test_packaging.py`): the built **wheel** and **sdist** each contain the license
file(s); metadata declares `GPL-3.0-only`; the console scripts are declared. Build into a temp
directory and inspect the actual archives — **not** `pyproject.toml`. Reading the source of truth
you already control proves nothing about the artifact.
**Green**: whatever packaging configuration is needed.
Commit: `build: include license files in wheel and sdist`.

### Task 3 — Clean-environment install and smoke test
**Red/Green**: a script that builds the wheel, installs it into a **fresh** venv (not the project
venv), and runs a headless smoke check — import the package, construct `MainWindow` under
`QT_QPA_PLATFORM=offscreen`, exit non-zero on failure. Must not import pyspark.
Commit: `ci: smoke test the installed wheel in a clean environment`.

### Task 4 — Build job in CI
Add a `build` job running Task 3 end to end and failing on any packaging or smoke failure.
Commit: `ci: add wheel build and install job`.

### Task 5 — Per-leg install audit as a test
**Red** (`tests/test_ci_workflow.py`): every job's `uv sync` line provides what that job's tooling
needs — `lint` must install whatever `ty` resolves; `test-duckdb` must **not** install the spark
extra; `test-spark` must; the new jobs likewise. Assert **properties**, not literal strings, and
assert `--locked` is **absent** with a comment explaining why.
Commit: `test(ci): assert each leg installs what its tooling needs`.

### Task 6 — Cross-platform Qt smoke job
Add a job on **ubuntu-latest, macos-latest, windows-latest**, one Python version, default
dependencies, running a small widget/integration subset offscreen. **Do not call `./run.sh` on
Windows** — invoke `uv` directly with the cache environment variables set explicitly.
This is the first real macOS/Windows verification in the project. If a platform cannot be made to
pass, **say so and leave it failing-but-visible rather than silently excluded** — a skipped
platform recorded as covered would repeat Phase 14's audit failure.
Commit: `ci: add cross-platform qt smoke job`.

### Task 7 — README rewrite
Document: installation (including `wherewolf[spark]` and the Java requirement), that `wherewolf`
opens a **native window**, keyboard shortcuts, native dialogs, result-grid behaviour, **the
distinction between local preview sorting and Apply Order to Query**, export (preview vs full,
and that full export streams), history, and the **GPL-3.0-only** license. Bump the
`cacheBuster` per AGENTS.md §13.
**Every claim must be true of the current code** — check each against the implementation, not
against an earlier README.
Commit: `docs: document the desktop workflow`.

### Task 8 — Migration notes from 0.5.x
`docs/MIGRATION-0.6.md`: the breaking change (`wherewolf` no longer opens a browser), what
happens to existing `~/.wherewolf/history.json` (v1 migrates on read — reference the Phase 11
behaviour), that pyspark is now an optional extra, and the Python floor.
Commit: `docs: add 0.5.x to 0.6.0 migration notes`.

### Task 9 — Changelog and release workflow
Update the changelog for the unreleased 0.6.0 section. Review `.github/workflows/release.yml` for
correctness **without triggering it**. **Do not bump the version.**
Commit: `docs: prepare the 0.6.0 changelog`.

### Task 10 — Manual acceptance checklist
`docs/review/manual-acceptance-checklist.md`: every `MANUAL` item from the parity audit plus
Section 22.5's cross-platform items, each as **exact steps and expected result**, with an
unchecked box and space for the platform and date. This is what the maintainer executes before
release.
Commit: `docs: add the manual acceptance checklist`.

### Task 11 — Close out
Finalise the session log with measured results and a clear statement of what remains gated on the
maintainer.
Commit: `docs: close out the release candidate session`.

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

### V1 — Suite and gates, both interpreters, both tiers
```bash
./run.sh uv run pytest -q                          # 3.14 default
./run.sh uv run pytest -q -m spark                 # spark tier
scripts/orchestration/run-quality-gates
./run.sh uv run --python 3.12 pytest -q --no-cov   # 3.12 default
./run.sh uv sync --all-extras --dev --python 3.14  # restore
```

### V2 — The artifacts contain the license (exit criterion)
Inspect the **built wheel and sdist archives**, not `pyproject.toml`. Paste the file listing
showing the license file in each. **Failure looks like:** asserting the declaration rather than
the artifact.

### V3 — Clean install actually works (exit criterion)
The wheel installs into a fresh venv and the smoke test passes there. Paste the venv path to
show it is not the project venv. Confirm pyspark is **not** pulled in by a default install.

### V4 — Cross-platform job runs on all three OSes
Paste the job matrix and the per-OS conclusions from a real run. **Failure looks like:** a
platform silently excluded, or a job that passes because it skipped everything.

### V5 — Per-leg install audit passes
Task 5's test passes and would fail if a leg lost an install its tooling needs.

### V6 — Documentation matches the code (exit criterion)
Spot-check at least six README claims against the implementation — the sorting distinction, the
export behaviour, the Spark extra, the shortcuts, the license, and the entry point. **Failure
looks like:** documenting intended behaviour rather than actual.

### V7 — Nothing was released
```bash
git diff dev..HEAD -- pyproject.toml | grep -E "^\+version" || echo "OK: no version bump"
git tag --points-at HEAD                                  # must be empty
```
The version must still be **0.5.2**. No tag, no `main` change.

### V8 — Mutation checks
**Commit first**; confirm each applied (`git diff --quiet` false); `--color=no`; revert between;
`git status --short` clean. **Record the node id you observed.**

1. Remove the license file from the wheel build → the V2 packaging test must FAIL.
2. Make the clean-env smoke test import pyspark → the default-install test must FAIL.
3. Give `test-duckdb` the spark extra → Task 5's audit test must FAIL.

### V9 — No 3.14-only syntax
```bash
grep -rn "except [A-Za-z_.]*, [A-Za-z_.]*:" src/ tests/ || echo "OK: none"
```

### V10 — No native crash regression
```bash
scripts/check_flake.sh 25    # twice; 50 runs total
```
0 crashes in 50. Preserve per-run logs.

### Deferred and explicitly NOT verified
- **The manual acceptance matrix is unsigned.** It is a release gate for the maintainer.
- **No performance measurement.** Section 22.6's targets are unmeasured; do not imply otherwise.
- The cross-platform job proves the app **constructs and passes a test subset** on macOS and
  Windows. It does **not** prove native dialogs, clipboard, or drag/drop behave correctly there —
  those remain manual.

## Constraints

**Do not bump the version. Do not tag. Do not touch `main`. Do not sign off the manual matrix.**
Do not reintroduce `uv sync --locked`. Do not remove `timid = true`. Do not disable coverage. Do
not skip, delete or xfail tests except via the documented `spark` marker. Do not run Spark work
outside the memory-bounded fixture.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished release-candidate
```

This writes:

```text
/tmp/wherewolf/release-candidate_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer release-candidate`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/release-candidate-review-*.md
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
   scripts/orchestration/clear-finished release-candidate
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
   git add docs/review/release-candidate-review-*.md
   git commit -m "docs(review): record release-candidate review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished release-candidate
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer release-candidate` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed release-candidate
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize release-candidate
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/release-candidate_finalized
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
scripts/orchestration/finalize release-candidate
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/release-candidate_finished
/tmp/wherewolf/release-candidate_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
