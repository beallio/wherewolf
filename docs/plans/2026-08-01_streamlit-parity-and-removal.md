# Phase 14 — Streamlit parity gate and removal

Slug: `streamlit-parity-and-removal`
Base branch: `dev`
Target release: 0.6.0 (minor). **Do not bump the version in this phase.**

## Context

This phase makes the native Qt application the only supported UI and deletes Streamlit.

It is the **riskiest phase in the migration**, and for a reason that is not technical: every
previous phase was additive with Streamlit still working as a fallback. This one removes the
fallback. If parity is overstated anywhere, a user loses a capability and has no way back short
of a version downgrade.

Goal, from the migration document: **`wherewolf` launches a native Qt window; no Streamlit
imports, dependencies, configuration, or supported code paths remain; full tests and quality
checks pass.**

### The parity gate comes first — nothing is deleted until it exists

Section 21 of the migration document lists roughly **sixty criteria marked Required**, and
states plainly: *"Every item marked Required blocks Streamlit removal."*

**This does not mean writing sixty new tests.** Phases 8–13 already cover most of them. It
means producing an honest audit, in this order:

1. map every Required criterion to the test node id that proves it, **or** mark it `GAP`,
   **or** mark it `MANUAL`;
2. fill the `GAP` items with real tests;
3. only then delete.

A criterion mapped to a test that does not actually assert it is worse than a `GAP`, because it
converts an unknown into a false assurance. If you cannot find a test that genuinely proves a
criterion, mark it `GAP` — that is the useful answer.

**Some criteria cannot be automated here and must be marked `MANUAL`**, not quietly claimed.
Section 22.1 says *"do not automate actual native dialogs in CI"*, and all Qt tests run
offscreen. At minimum these are manual: "no browser tab or local web server is started",
"UI remains responsive during query execution", "native multi-file dialog where supported", and
anything asserting real windowing behaviour. List them explicitly so the maintainer knows what
a human still needs to click before release.

### The deletion set — verified, not assumed

Inventory taken on `dev` @ `94a0bec`:

| file | status |
|---|---|
| `src/wherewolf/app.py` | Streamlit UI — delete |
| `src/wherewolf/cli.py` | launches `streamlit run` via subprocess — **rewrite**, do not delete |
| `src/wherewolf/engines.py` | `@st.cache_resource` factories; **imported only by `app.py`** and `tests/test_engines.py` — delete |
| `src/wherewolf/ui/file_browser.py`, `ui/results.py` | Streamlit-only — delete |
| `src/wherewolf/export/exporter.py` | byte-based; used only by `ui/results.py` and its own test (established in Phase 12) — delete |
| `.streamlit/` | delete |
| deps: `streamlit`, `streamlit-ace`, `playwright` | remove if nothing else uses them — **verify `playwright` before removing** |

**The desktop path does not import `engines.py`** — it uses `execution/registry.py`. That is
what makes this detachable. Confirm that claim yourself before deleting; if anything in
`desktop/` reaches into `engines.py`, stop and report.

Fifteen test files reference `streamlit` or `AppTest`. Some are Streamlit-only
(`test_app*.py`, `test_ui_branding.py`, `test_results.py`, `test_file_browser_*.py`). Others —
`test_history.py`, `test_models.py`, `test_excel_support.py`, `test_config_toml.py` — test
**shared** behaviour and merely touch Streamlit incidentally. **Do not delete a test because it
mentions Streamlit.** Read each one; keep what tests shared code, adapting it if needed.
Deleting a shared-behaviour test to make a grep come back clean would silently drop coverage.

### Entry points

`wherewolf` currently points at `wherewolf.cli:main`, which launches Streamlit. After this
phase it must launch the desktop app, and `python -m wherewolf` must do the same. Keep
`wherewolf-desktop` working as an alias so existing invocations do not break.

This is a **breaking change** for anyone relying on `wherewolf` opening a browser. The final
commit should be `feat!:` per the migration document.

### Dependency changes affect every CI leg, not just the test legs

Learned the hard way one phase ago: making pyspark optional broke the **lint** leg, because
`ty` could no longer resolve the import. That was caught only after merging.

Removing three dependencies changes what every leg can see. **Check each leg individually** —
`lint`, `test-duckdb`, `test-spark` — and confirm each still installs what its own tooling
requires. Do not assume a green local run generalises; local has everything installed.

### Commit granularity is a requirement in this phase, not a preference

The last two phases landed many tasks in single commits. Here that is genuinely costly: if
deleting the Streamlit path breaks something, the question is *which deletion did it*, and the
answer should come from one `git bisect` rather than an archaeology session in a large diff.

**One commit per task. Deletions get their own commits, separated by target.** This will be
checked in review.

### Python floor, crash history, repo mechanics

CI tests 3.12 and 3.14. No PEP 758 unparenthesized `except`. `timid = true` stays.
`./run.sh uv run --python 3.12 ...` re-syncs the shared venv — restore with
`./run.sh uv sync --all-extras --dev --python 3.14`. `scripts/check_tdd.sh` requires a flat
`tests/test_<basename>.py` per staged `src/**/*.py`. The pre-commit hook does `git add -u`.
No `Co-Authored-By:` or `Claude-Session:` trailers.

**V10 is mandatory this phase** — deleting code that constructs Qt objects can change teardown
ordering, and this project has a documented native-segfault history.

### Delegate low-level work to your subagents

Seven read-only `agent-memory` subagents are available (`~/.codex/agents/*.toml`), MCP on
`--tool-profile full`. **Surface what they return; do not act on it silently.**

- **`memory_researcher`** — before Task 2, ask for prior parity decisions, deferred items, and
  **failed approaches**. Several criteria reference behaviour decided in earlier phases; the
  audit is more accurate with that history. Report consequential claim IDs.
- **`memory_evidence_reviewer`** — if a remembered claim would let you mark a criterion as
  covered, audit it first. A stale claim becomes a false parity assertion here.

Do **not** invoke `memory_curator` or `memory_lifecycle_manager`; nothing here authorizes a
memory write.

### Recording rule

**"Not measured" is a complete and acceptable answer**, and in this phase so is `GAP` and
`MANUAL`. Record measured values, never adjectives. After any change you report, run the
command that would fail if it had not landed and paste that output.

### Baseline

`dev` @ `94a0bec`: **364 passed, 7 deselected** (default tier) on both 3.12 and 3.14; Spark tier
7 passed; CI green on `lint`, `test-duckdb (3.12/3.14)`, `test-spark (3.12/3.14)`. Record your
own baseline in Task 1.

## Orchestration Contract

**Slug:** `streamlit-parity-and-removal`

**Plan file:**

```text
docs/plans/2026-08-01_streamlit-parity-and-removal.md
```

**Implementation branch:**

```text
feat/streamlit-parity-and-removal
```

**Round-complete marker:**

```text
/tmp/wherewolf/streamlit-parity-and-removal_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/streamlit-parity-and-removal_finalized
```

**Review notes:**

```text
docs/review/streamlit-parity-and-removal-review-*.md
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
git checkout -b feat/streamlit-parity-and-removal
```

Commit this plan first:

```bash
git add docs/plans/2026-08-01_streamlit-parity-and-removal.md
git commit -m "docs(plan): add streamlit-parity-and-removal implementation plan"
```

---

## Implementation Tasks

One commit per task. **Tasks 2–3 must complete before any deletion.**

### Task 1 — Session log and baseline
`docs/agent_conversations/2026-08-01_streamlit-parity-and-removal.md` with the baseline commit
and measured tallies on both interpreters and both tiers. No source changes.
Commit: `docs: record streamlit removal baseline`.

### Task 2 — The parity audit (the gate)
Produce `docs/review/streamlit-parity-audit.md`: every Required criterion from Section 21.1–21.9,
each mapped to **a test node id**, `GAP`, or `MANUAL` with a one-line reason. No source changes,
no deletions.
Commit: `docs: audit streamlit parity criteria`.

### Task 3 — Fill the gaps
Add real regression tests for every `GAP`. If a gap cannot be closed automatically, move it to
`MANUAL` **and say why** rather than leaving it unaddressed.
Commit: `test: close streamlit parity gaps` (or one commit per coherent group).

### Task 4 — Desktop entry points
**Red**: `wherewolf` and `python -m wherewolf` both reach the desktop entry; `wherewolf-desktop`
still works.
**Green**: rewrite `cli.py` to launch the desktop app; add `__main__.py`.
Commit: `feat(cli): launch the desktop application`.

### Task 5 — Delete the Streamlit UI modules
Delete `src/wherewolf/app.py`, `src/wherewolf/ui/file_browser.py`, `src/wherewolf/ui/results.py`
and their Streamlit-only tests.
Commit: `refactor!: remove the streamlit ui modules`.

### Task 6 — Delete the Streamlit engine factory
Delete `src/wherewolf/engines.py` and adapt `tests/test_engines.py`. **Confirm first** that
nothing under `desktop/` imports it.
Commit: `refactor!: remove the streamlit engine cache factory`.

### Task 7 — Delete the byte-based exporter
Delete `src/wherewolf/export/exporter.py` and `tests/test_exporter.py` once no consumer remains.
Verify the desktop export path is untouched.
Commit: `refactor!: remove the byte-based exporter`.

### Task 8 — Delete configuration and dependencies
Delete `.streamlit/`; remove `streamlit`, `streamlit-ace`, and `playwright` from
`pyproject.toml` **after confirming nothing else uses them**. Re-lock.
Commit: `build!: drop streamlit dependencies`.

### Task 9 — Sweep for residue
Search for `streamlit`, `st.`, `streamlit_ace`, `AppTest`, and obsolete session-state
terminology across the repository, including docs and CI. Report what remains and why (historical
references in `docs/review/` and session logs are fine and should stay).
Commit: `chore: remove streamlit residue`.

### Task 10 — CI legs
Verify each leg still installs what its tooling needs after the dependency removal. Remove any
now-dead setup steps.
Commit: `ci: update legs after streamlit removal`.

### Task 11 — README and close out
Document that `wherewolf` now opens a native window, the breaking change, and the manual parity
items a human must still verify. Bump the README `cacheBuster`. Finalise the session log.
Commit: `docs: document the desktop-only application`.

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

### V2 — The audit is honest
Every Required criterion is `test node id`, `GAP` (closed in Task 3), or `MANUAL` with a reason.
**Failure looks like:** a criterion mapped to a test that does not actually assert it. Spot-check
your own mappings by opening the tests you cite.

### V3 — Entry points
`wherewolf`, `python -m wherewolf`, and `wherewolf-desktop` all reach the desktop entry. Assert
the console-script target, not just that a module imports.

### V4 — No Streamlit remains (exit criterion)
```bash
grep -rn "streamlit\|streamlit_ace\|AppTest" src/ tests/ pyproject.toml .github/ || echo "clean"
```
Historical references under `docs/` are expected and fine. **Failure looks like:** a residual
import, dependency, or config file.

### V5 — No shared coverage was lost
Report the test tally before and after. A drop is expected — Streamlit tests are being deleted —
but **account for it**: state how many tests were removed and confirm each removed test covered
Streamlit-only behaviour. **Failure looks like:** an unexplained tally drop, or a shared-behaviour
test deleted because it mentioned Streamlit.

### V6 — Every CI leg still installs what it needs
State, per leg, what it installs and what its tooling requires. `lint` needs whatever `ty` must
resolve. This is where the previous phase broke.

### V7 — Mutation checks
**Commit first**; confirm each applied (`git diff --quiet` false); `--color=no`; revert between;
`git status --short` clean. **Record the node id you observed.**

1. Point `wherewolf` back at a Streamlit launcher → the entry-point test must FAIL.
2. Restore a `streamlit` import in `src/` → the V4 residue check must FAIL.
3. Break one criterion the audit claims is covered (pick one from 21.5 or 21.7) → its cited test
   must FAIL. This validates the audit itself, not just the code.

Mutation 3 is the important one — it is the only check that the parity matrix means anything.

### V8 — No 3.14-only syntax
```bash
grep -rn "except [A-Za-z_.]*, [A-Za-z_.]*:" src/ tests/ || echo "OK: none"
```

### V9 — Commit granularity
`git log --oneline dev..HEAD` shows one commit per task, with deletions separated by target.

### V10 — No native crash regression (mandatory)
```bash
scripts/check_flake.sh 25    # twice; 50 runs total
```
0 crashes in 50. Preserve per-run logs — `check_flake.sh` overwrites its log every run. A single
clean 25 proves little: at a 6% rate, 0/25 happens ~21% of the time for code that still crashes.

### Deferred and explicitly NOT verified
- **The `MANUAL` parity items have not been verified by a human.** List them; they are a
  release gate, not a test gate.
- No performance measurement. macOS and Windows unverified. Spark verified on Linux with one JDK.

## Constraints

Do not delete a test merely because it mentions Streamlit — read it first. Do not mark a
criterion covered without opening the test you cite. Do not remove `timid = true`. Do not disable
coverage. Do not skip, delete or xfail tests except the Streamlit-only ones this phase removes by
design. Do not touch `main`. Do not bump the package version — 0.6.0 belongs to Phase 15.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished streamlit-parity-and-removal
```

This writes:

```text
/tmp/wherewolf/streamlit-parity-and-removal_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer streamlit-parity-and-removal`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/streamlit-parity-and-removal-review-*.md
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
   scripts/orchestration/clear-finished streamlit-parity-and-removal
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
   git add docs/review/streamlit-parity-and-removal-review-*.md
   git commit -m "docs(review): record streamlit-parity-and-removal review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished streamlit-parity-and-removal
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer streamlit-parity-and-removal` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed streamlit-parity-and-removal
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize streamlit-parity-and-removal
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/streamlit-parity-and-removal_finalized
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
scripts/orchestration/finalize streamlit-parity-and-removal
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/streamlit-parity-and-removal_finished
/tmp/wherewolf/streamlit-parity-and-removal_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
