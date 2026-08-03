# Phase 11 — History v2 and persistent preferences

Slug: `history-v2-and-preferences`
Base branch: `dev`
Target release: 0.6.0 (minor). **Do not bump the version in this phase.**

## Context

Phases 8–10 delivered execution, the result grid, and the analytical panels. This phase
preserves work **across sessions**: a durable, versioned query history that can be restored
without ambiguity, and desktop state that survives a restart.

Goal, from the migration document: **existing history is preserved; restart restores normal
desktop preferences; duplicate display labels cannot select the wrong record.**

### This phase owns `storage/history.py` — read this first

Every previous plan listed `src/wherewolf/storage/` as protected Streamlit path. **That
protection is lifted for this phase only, for `history.py` only.** Phase 11 cannot be done
without changing it.

The protection is replaced by a **compatibility requirement**, which is stricter and testable.
`src/wherewolf/app.py:313-321` reads history directly:

```python
history = history_manager.get_all()
history_labels = [f"{h['timestamp'][:16]} - {h['query'][:30]}..." for h in history]
selected_history = st.selectbox("Select from History", ["Select..."] + history_labels)
if selected_history != "Select...":
    idx = history_labels.index(selected_history)
    st.session_state.pending_query = history[idx]["query"]
```

So every record `get_all()` returns must still expose `timestamp` (ISO-8601, whose first 16
characters remain a usable label) and `query`. **You may not modify `app.py`** — it stays on the
v1 read shape. If `get_all()` stops returning those keys, Streamlit breaks.

### The bug this phase exists to fix

Look at that snippet again. `history_labels.index(selected_history)` returns the **first**
matching label. Two queries run in the same minute whose first 30 characters match produce
**identical labels**, and selecting the second silently restores the first.

That is a real, live bug — not a hypothetical. The Qt History dock must **select by UUID**, not
by label, not by list position. That is the whole point of v2.

You are **not** asked to fix `app.py`; it is deleted in Phase 14. You are asked to ensure the
new dock cannot reproduce the defect, and to prove it with a test that would fail if selection
were label- or index-based.

### What already exists — use it, do not rebuild it

- **`storage/history.py`** — `HistoryManager` with `DEFAULT_PATH = ~/.wherewolf/history.json`,
  `add_entry(engine, query, path="", catalog=None)`, `get_all()`, `clear()`.
  - **The atomic write already works** (`tempfile.mkstemp` + `os.replace`) and is covered by
    `tests/test_history_atomicity.py`. **Keep it. Do not regress it.**
  - The 100-record cap already exists.
  - The timestamp is already `datetime.now().astimezone().isoformat()`, and its own comment
    says this was made unambiguous *specifically for the schema-v2 migration*. The groundwork
    was laid; use it.
- **`services/settings_service.py`** — `SettingsService` over `QSettings`, already
  schema-versioned, already round-tripping window geometry, window state, splitter sizes,
  editor font size, last dataset directory, completion threshold and completion enabled.
  **It is largely complete.** This phase adds corrupt-value fallback and dock state — do not
  rewrite what works.
- **`desktop/main_window.py`** — already saves geometry/state/splitter/font in `closeEvent`.
  Restore is the missing half.
- **`domain/models.py`** — reuse existing types. Do not invent a parallel record type if an
  existing one fits.

### Known defect you must fix as part of Task 4

`get_all()` currently does:

```python
except (OSError, json.JSONDecodeError):
    return []
```

A **single** corrupt byte anywhere in the file therefore discards the user's **entire** history
silently. That is the "malformed-record isolation" requirement: one unreadable record must not
destroy the other ninety-nine. Losing user data quietly is the worst failure mode in this
phase — weight it accordingly.

### Known defects you must NOT fix here

- `execution/spark_engine.py` swallows exceptions in `get_schema`. Phase 13.
- `app.py`'s label-based selection. Phase 14 deletes it.
- Export is Phase 12.

### Hard constraint: Streamlit must keep working

Do not modify `src/wherewolf/app.py`, `engines.py`, `ui/`, `export/`, `constants.py` or
`.streamlit/`. `storage/history.py` is the **single** exception, and only under the
compatibility requirement above.

### Python floor: 3.12 AND 3.14

CI tests both legs. No PEP 758 unparenthesized `except` — `except (OSError, ValueError):`, not
`except OSError, ValueError:`, which is a SyntaxError on 3.12. No 3.13+/3.14-only constructs.
Let `ruff check --fix` and `ruff format` enforce it rather than hand-writing modern syntax.

`./run.sh uv run --python 3.12 ...` re-syncs the **shared** `UV_PROJECT_ENVIRONMENT` at
`/tmp/wherewolf/.venv`. Afterwards run `./run.sh uv sync --all-extras --dev --python 3.14`, or
every later measurement silently runs on the wrong interpreter.

### The crash history you must respect

A native segfault was root-caused in Phase 8: `SchemaWorker` QThreads destroyed while running,
posted events delivered into freed memory. `MainWindow.closeEvent` drains schema workers and
calls `QueryController.shutdown()`.

This phase adds a **dock** and touches `closeEvent` (restore + Reset Layout). Any QObject
parented to a transient window must not outlive it. **If you touch `closeEvent`, V10 is
mandatory.** Do not remove `timid = true` from `pyproject.toml` — it is load-bearing on 3.14.

### Repo mechanics that will fail your commits

- `scripts/check_tdd.sh` requires a **flat** `tests/test_<basename>.py` per staged
  `src/**/*.py`. A new `src/wherewolf/desktop/widgets/history_dock.py` needs
  `tests/test_history_dock.py`.
- The pre-commit hook runs `ruff check`, `ruff format`, `ty check`, `pytest` and
  `check_tdd.sh`, and does `git add -u`, sweeping modified tracked files into your commit.
  Stage deliberately.
- Caches live under `/tmp/wherewolf`. Run project commands through `./run.sh`.
- Commit messages must NOT contain `Co-Authored-By:` or `Claude-Session:` trailers.

### Recording rule — read before writing the session log

**"Not measured" is a complete and acceptable answer.** If you did not run something, say so.
A plausible-looking number never observed is the one thing the record cannot absorb. After any
change you report, run the command that would fail if it had not landed and paste that output.
Record measured values, never adjectives like "all green".

### Baseline

`dev` @ `c4f57e0`: **307 passed, 1 skipped** on both 3.12 and 3.14; CI green on `lint`,
`test (3.12)`, `test (3.14)`. Record your own baseline in Task 1.

## Orchestration Contract

**Slug:** `history-v2-and-preferences`

**Plan file:**

```text
docs/plans/2026-08-01_history-v2-and-preferences.md
```

**Implementation branch:**

```text
feat/history-v2-and-preferences
```

**Round-complete marker:**

```text
/tmp/wherewolf/history-v2-and-preferences_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/history-v2-and-preferences_finalized
```

**Review notes:**

```text
docs/review/history-v2-and-preferences-review-*.md
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
# ORCH_LOCAL_ONLY: local trial branch, skipping origin pull
git checkout -b feat/history-v2-and-preferences
```

Commit this plan first:

```bash
git add docs/plans/2026-08-01_history-v2-and-preferences.md
git commit -m "docs(plan): add history-v2-and-preferences implementation plan"
```

---

## Implementation Tasks

Each task is one commit, Red before Green. Tasks 2–6 are **Qt-free** — the entire storage
layer lands testable without a GUI before any widget exists.

### Task 1 — Session log and baseline
Create `docs/agent_conversations/2026-08-01_history-v2-and-preferences.md` with the baseline
commit and the measured tally on **both** interpreters. No source changes.
Commit: `docs: record history v2 baseline`.

### Task 2 — v2 record shape with a stable id
**Red** (`tests/test_history.py`): a new entry carries a **UUID** and a schema version; two
entries added in the same second with identical query text have **different** ids; the record
still exposes `timestamp` and `query` at the top level for the Streamlit reader.
**Green**: extend the record written by `add_entry`. State the version marker you chose.
Commit: `feat(history): add versioned history records with stable ids`.

### Task 3 — v1 → v2 migration
**Red**: a v1 file (a bare JSON list, no version, no ids) is migrated on read — every record
survives, **order is preserved**, and each gains a stable id; migration is **idempotent**
(running twice changes nothing); an already-v2 file is untouched; the original file is not
destroyed if migration fails partway.
**Green**: migrate on load. **Existing history is preserved** is an exit criterion — a user
with 100 records must still have 100.
Commit: `feat(history): migrate v1 history to v2 on load`.

### Task 4 — Malformed-record isolation
**Red**: a file where **one** record is corrupt still returns the others; a wholly unparseable
file returns empty **without** deleting the file; a record missing a required key is skipped
rather than crashing the read. Assert the surviving **count and contents**, not just "no
exception".
**Green**: isolate per-record failures. Replace the blanket
`except (OSError, json.JSONDecodeError): return []`.
Commit: `fix(history): isolate malformed records instead of discarding history`.

### Task 5 — UUID lookup and the record cap
**Red**: `get_by_id()` returns the right record; an unknown id returns `None` rather than
raising; the 100-record cap still holds after migration; the cap evicts **oldest first**.
**Green**: add lookup by id. Keep the existing cap behaviour.
Commit: `feat(history): add id-based lookup`.

### Task 6 — Streamlit compatibility and atomicity, proven
**Red**: a test asserting `get_all()` records still satisfy the exact `app.py` access pattern —
`h["timestamp"][:16]` yields a sensible label and `h["query"]` is the SQL — **for both a
migrated v1 file and a fresh v2 file**; the existing atomic-write guarantee still holds.
**Green**: no change expected. If one is needed, that is a real finding — record it.
Commit: `test(history): guard streamlit read compatibility and atomic writes`.

### Task 7 — History dock, selecting by id
**Red** (`tests/test_history_dock.py`, `qtbot`): the dock lists records; **two records with
identical display labels are individually selectable and return different records** — this is
the exit criterion and the test must fail if selection is by label or by list index.
**Green**: `src/wherewolf/desktop/widgets/history_dock.py`, parented properly, carrying the id.
Commit: `feat(desktop): add history dock`.

### Task 8 — Restore SQL from a history record
**Red**: restoring places the record's SQL in the editor and **does not** execute it, and does
not alter the current catalog.
**Green**: wire the dock to the editor by signal.
Commit: `feat(desktop): restore SQL from history`.

### Task 9 — Restore catalog, with missing files reported
**Red**: restoring a record whose catalog references a **deleted** file reports the missing
path clearly and still restores the files that do exist; nothing raises; the user is told what
is missing.
**Green**: restore what can be restored, report the rest.
Commit: `feat(desktop): restore history catalog and report missing files`.

### Task 10 — Settings round trip and corrupt-value fallback
**Red**: each setting round-trips; a **corrupt or wrong-typed** stored value falls back to the
documented default instead of raising; the fallback is asserted per setting, not once
generally.
**Green**: harden `SettingsService`. Do not rewrite the working key scheme.
Commit: `fix(settings): fall back safely on corrupt stored values`.

### Task 11 — Restore window, dock and splitter state
**Red**: geometry, window state, dock layout and splitter sizes restore on construction; a
first run with **no** stored settings produces a sane default layout rather than a broken one.
**Green**: restore in `MainWindow`. `closeEvent` already saves — do not duplicate that.
Commit: `feat(desktop): restore window and dock layout on startup`.

### Task 12 — Reset Layout and Clear History
**Red**: Reset Layout returns docks and splitters to defaults and persists that; Clear History
empties the store **and** the dock, and the file remains valid afterwards (not deleted, not
corrupt). Destructive actions must leave a readable file.
**Green**: add both actions.
Commit: `feat(desktop): add reset layout and clear history actions`.

### Task 13 — README and close out
Document history v2, the migration, the dock, and the preferences that persist. Bump the README
`cacheBuster` per AGENTS.md §13. Finalise the session log with measured results.
Commit: `docs: document history v2 and desktop preferences`.

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

State sample sizes and decision rules **before** measuring. Record measured outcomes.

### V1 — Suite and gates, on BOTH interpreters
```bash
./run.sh uv run pytest -q                         # 3.14 — record the tally
scripts/orchestration/run-quality-gates           # must exit 0
./run.sh uv run --python 3.12 pytest -q --no-cov  # 3.12 — record the tally
./run.sh uv sync --all-extras --dev --python 3.14 # restore the dev interpreter
```

### V2 — Streamlit still works (the diff is NOT empty this phase)
`storage/history.py` legitimately changes here, so the usual empty-diff check does not apply.
Instead:
```bash
git diff dev..HEAD -- src/wherewolf/app.py src/wherewolf/engines.py src/wherewolf/ui/ \
  src/wherewolf/export/ src/wherewolf/constants.py .streamlit/   # MUST be empty
./run.sh uv run pytest -q --no-cov tests/test_app.py tests/test_app_flow.py \
  tests/test_app_cancel.py tests/test_history.py tests/test_history_atomicity.py
```
**Failure looks like:** any change to `app.py`, or a Streamlit history test failing.

### V3 — Existing history is preserved (exit criterion)
Migrate a realistic v1 file with **100** records and assert all 100 survive with order intact.
Run the migration **twice** and assert the second run is a no-op. **Failure looks like:**
testing migration with a single record, which cannot detect ordering or cap bugs.

### V4 — Duplicate labels cannot select the wrong record (exit criterion)
Build two records whose `timestamp[:16]` **and** `query[:30]` are identical, select the second
in the dock, and assert the **second** record's full content comes back. **Failure looks
like:** a test with distinguishable records, which passes even with label-based selection.

### V5 — Malformed-record isolation
Assert surviving record **count and contents** with one corrupt record among several, and that
a wholly unreadable file does not delete the file. **Failure looks like:** asserting only that
no exception was raised.

### V6 — Atomic write preserved
`tests/test_history_atomicity.py` must still pass unmodified. If you changed it, explain why.

### V7 — Settings fallback
Assert per-setting fallback on a corrupt stored value. **Failure looks like:** one generic test
standing in for all settings.

### V8 — Mutation checks: prove the new tests bite
**Commit first.** Confirm each mutation applied (`git diff --quiet` must be **false**) before
trusting a "no bite"; grep with `--color=no`; revert between each; `git status --short` clean
afterwards. **Record the failing node id you actually observed.**

1. Select history by list index instead of id → the duplicate-label test must FAIL.
2. Drop the id from new records → the stable-id test must FAIL.
3. Return `[]` on any malformed record → the isolation test must FAIL.
4. Make migration non-idempotent (re-migrate every load) → the idempotency test must FAIL.
5. Evict newest instead of oldest at the cap → the cap test must FAIL.
6. Raise instead of falling back on a corrupt setting → the fallback test must FAIL.

Mutation 1 is the most important in this phase — it is the defect the design exists to prevent.

### V9 — No 3.14-only syntax
```bash
grep -rn "except [A-Za-z_.]*, [A-Za-z_.]*:" src/ tests/ || echo "OK: none"
```

### V10 — No native crash regression (mandatory if `closeEvent` changed)
```bash
scripts/check_flake.sh 25    # run TWICE; 50 runs total
```
**Pass:** 0 native crashes in 50.

`check_flake.sh` overwrites `/tmp/wherewolf/flake-guard-last.txt` every run — **preserve
per-run logs** or you report a count with no evidence. A single clean batch of 25 proves
little: at a 6% rate, `0/25` happens ~21% of the time for code that still crashes.

### Deferred and explicitly NOT verified
- **No human has seen the dock or a restored layout.** All Qt tests are offscreen. Say so.
- **No migration has been run against a real user's history file.** Say so.
- No performance measurement.
- Export is Phase 12, Spark Phase 13, Streamlit removal Phase 14.
- macOS and Windows unverified — `QSettings` backends differ per platform and this phase is
  verified on Linux only. State that plainly.

## Constraints

Do not remove `timid = true`. Do not disable coverage. Do not skip, delete or xfail tests. Do
not modify `app.py` or any Streamlit path beyond `storage/history.py`. Do not regress the
existing atomic write. Do not touch `main`. Do not bump the package version — 0.6.0 belongs to
the final cutover.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished history-v2-and-preferences
```

This writes:

```text
/tmp/wherewolf/history-v2-and-preferences_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer history-v2-and-preferences`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/history-v2-and-preferences-review-*.md
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
   scripts/orchestration/clear-finished history-v2-and-preferences
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
   git add docs/review/history-v2-and-preferences-review-*.md
   git commit -m "docs(review): record history-v2-and-preferences review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished history-v2-and-preferences
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer history-v2-and-preferences` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed history-v2-and-preferences
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize history-v2-and-preferences
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/history-v2-and-preferences_finalized
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
scripts/orchestration/finalize history-v2-and-preferences
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/history-v2-and-preferences_finished
/tmp/wherewolf/history-v2-and-preferences_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
