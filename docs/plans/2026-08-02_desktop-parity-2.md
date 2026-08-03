# Plan: Reachable commands, preferences and affordances (desktop-parity-2)

## Context

Round one closed the defects the maintainer reported directly. A three-angle audit
afterwards (Streamlit UI surface recovered from git, dead-code reachability, and
docs-claims-vs-code) found a second tier: **features that are fully implemented and
tested but have no user-facing entry point**, plus affordances Streamlit had that the Qt
port dropped.

This is the same pattern that produced the dead `TranslationPanel` and `SchemaPanel`:
working code behind no door. The tests for these helpers already pass today.

**Already fixed on `dev` — do not revisit:** the pyarrow mimalloc import in
`execution/registry.py:23`, export source-warning display in `_on_export_result`, and
the removal of `DontConfirmOverwrite` from the export dialog.

### Defects to close

**E1 — editor and preview commands exist but are unreachable.**

| helper | location | missing entry point |
|---|---|---|
| `find_text`, `replace_next`, `replace_all` | `desktop/widgets/sql_editor.py:420+` | no Find/Replace command or dialog |
| Select All | — | promised at migration plan:680, absent from Edit menu |
| `set_filter_text`, `filter_text`, `toggle_sort` | `desktop/models/typed_sort_proxy_model.py:17+` | no preview search bar (promised at migration plan:1140) |
| `write_selection` | `services/preview_export.py:26` | no "Export Selection" command (promised at path-based-export plan:228) |
| `call_tip` | `services/completion_service.py:345` | no call-tip hookup in the editor |
| `add_diagnostic` | `desktop/widgets/messages_panel.py:23` | nothing routes diagnostics into the Messages tab |

**E2 — no Preferences UI.** `README.md:66` claims "editor font size ... and completion
preferences are persisted". `services/settings_service.py:152,162`
(`save_completion_threshold`, `save_completion_enabled`) have **no production caller**,
and no menu exposes font size or completion settings. Either add the UI or correct the
README — do not leave the claim standing over absent behaviour.

**E3 — missing empty states, feedback and gating**, all present in Streamlit:

| behaviour | Streamlit source |
|---|---|
| "No datasets loaded" empty state | `app.py:243-259` |
| "No history yet" empty state | `app.py:313-329` |
| "Please add a dataset to begin" initial banner | `app.py:481-482` |
| "Added `<alias>` to catalog." success feedback | `app.py:237-241` |
| Run disabled while the catalog is empty | `app.py:391-397` |
| truncated-result explanation before offering full export | `ui/results.py:111-155` |
| expandable raw error details | `ui/results.py:157-160` |
| window title/branding and version display | `app.py:22-26`, `app.py:206-217` |

**E4 — Spark availability is not actually checked.** `execution/registry.py:414`:

```python
def _is_spark_available(self) -> bool:
    return util.find_spec("pyspark") is not None
```

With the extra installed but no JDK, Spark appears selectable and fails at query time
with a confusing stack. `docs/review/manual-acceptance-checklist.md:102` states Spark
should require the extra **and** Java.

**E5 — smaller promised-but-absent items.** Catalog "Reveal in Finder/Explorer/file
manager" (migration plan:803; `desktop/widgets/catalog_dock.py:57` omits it); Help menu
"Documentation" and "Open-Source Licenses" (migration plan:711; only About exists);
Streamlit's "Show Hidden Files" toggle (`ui/file_browser.py:74-100`).

**Slug used throughout this plan:** `desktop-parity-2`

---

## Orchestration Contract

**Slug:** `desktop-parity-2`

**Plan file:**

```text
docs/plans/2026-08-02_desktop-parity-2.md
```

**Implementation branch:**

```text
feat/desktop-parity-2
```

**Round-complete marker:**

```text
/tmp/wherewolf/desktop-parity-2_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/desktop-parity-2_finalized
```

**Review notes:**

```text
docs/review/desktop-parity-2-review-*.md
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
git pull --ff-only origin dev
git checkout -b feat/desktop-parity-2
```

Commit this plan first:

```bash
git add docs/plans/2026-08-02_desktop-parity-2.md
git commit -m "docs(plan): add desktop-parity-2 implementation plan"
```

---

## Implementation Tasks

One commit per task, Conventional Commits, TDD throughout: write the failing test, watch
it fail, then implement.

**The binding rule from round one still applies and is why this plan exists:** a test
must reach the feature from `MainWindow` the way a user would. A test that constructs a
helper directly, or asserts a menu object exists rather than that it has actions, would
have passed against every defect listed here. Round one's tests were checked by mutation;
yours will be too.

### Task 1 — Find / Replace / Select All (E1)

Add Edit-menu commands and a Find/Replace dialog driving the existing `find_text`,
`replace_next`, `replace_all`. Add Select All. Test by driving the dialog from
`MainWindow` and asserting the editor text actually changes — not that the methods exist.

### Task 2 — preview search bar (E1)

Add a search/filter control above the results grid, wired to
`TypedSortProxyModel.set_filter_text`, with a clear action that restores all rows
(migration plan:1140). Test that filtering reduces the visible row count and that
clearing restores the original count.

### Task 3 — Export Selection (E1)

Add an "Export Selection" command wired to `preview_export.write_selection`, honouring
the visual order the path-based-export plan promised. Test on the produced file's
contents and row order, not on call arguments.

### Task 4 — call tips and diagnostics routing (E1)

Hook `SqlCompletionService.call_tip` into the editor so call tips appear, and route
diagnostics through `MessagesPanel.add_diagnostic` so they reach the Messages tab. Test
that a diagnostic raised during a real run becomes visible in the panel.

### Task 5 — Preferences (E2)

Add a Preferences dialog covering editor font size and completion settings, persisted via
the existing `SettingsService` methods that currently have no callers. Test that changing
a preference survives a settings round-trip **and** takes effect in the editor. If you
choose not to build the completion controls, you must instead correct `README.md:66` —
leaving the claim over absent behaviour is not an acceptable outcome.

### Task 6 — empty states, feedback and Run gating (E3)

Implement the E3 table. Run must be disabled with an empty catalog and re-enabled when a
dataset is added — test both transitions. Give the window a real title including the
version. Show why a result was truncated before offering the full export. Make raw error
details expandable rather than dumped or hidden.

### Task 7 — Spark availability (E4)

Make `_is_spark_available` require a usable Java runtime as well as `pyspark`. Test all
four combinations of (pyspark present/absent) x (Java present/absent) by faking the
probe; the Spark option must be unavailable unless both hold, with a message saying which
is missing. Do not make the probe run a JVM on import — it must stay cheap.

### Task 8 — reveal, help entries, hidden files (E5)

Catalog context-menu "Reveal in file manager" (platform-appropriate, and test the command
it would run rather than launching a file manager); Help menu "Documentation" and
"Open-Source Licenses"; a "Show Hidden Files" toggle on the dataset chooser.

### Cross-cutting requirements

- Do not weaken, skip or delete any existing test.
- Do not remove `timid = true` from `[tool.coverage.run]`.
- Do not remove the `pyarrow` import in `src/wherewolf/execution/registry.py`.
- Do not reintroduce `DontConfirmOverwrite`.
- Do not bump the version, tag, or touch `main`.
- `ty` checks the whole repo including `tests/`, not just `src/`. Run
  `./run.sh uv run ty check .` before you commit — a `src/`-only check passes while the
  pre-commit hook fails.

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

```bash
./run.sh uv run ruff check . && ./run.sh uv run ruff format --check .
./run.sh uv run ty check .
./run.sh uv run pytest
```

Then demonstrate each defect is closed, recording real output in your session log:

1. Find/Replace — editor text before and after a replace-all driven from the menu.
2. Preview filter — visible row count before filtering, filtered, and after clear.
3. Export Selection — the produced file's row count and first rows.
4. Call tips / diagnostics — the diagnostic text visible in the Messages panel.
5. Preferences — the persisted value after a round-trip, and the editor property it changed.
6. Empty states — `run.isEnabled()` with an empty catalog and after adding a dataset;
   the window title string.
7. Spark — the availability result and message for all four pyspark/Java combinations.
8. Reveal/help/hidden — the command string Reveal would execute, and the Help menu actions.

**Negative controls are mandatory for tasks 1, 2, 6 and 7.** Mutate the implementation to
reintroduce each defect, confirm the corresponding test fails, and paste the failing
output. Round one's three mutations each failed exactly one test while leaving the rest
green — match that standard, since a mutation that fails twenty tests only proves the
suite is coupled.

## Deferred verification

Native file-manager launching, real dialog appearance, and call-tip rendering are manual
maintainer checks. Record them in `docs/review/manual-acceptance-checklist.md` rather
than claiming them verified. macOS and Windows remain covered only by the offscreen
`qt-smoke` CI job.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished desktop-parity-2
```

This writes:

```text
/tmp/wherewolf/desktop-parity-2_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer desktop-parity-2`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/desktop-parity-2-review-*.md
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
   scripts/orchestration/clear-finished desktop-parity-2
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
   git add docs/review/desktop-parity-2-review-*.md
   git commit -m "docs(review): record desktop-parity-2 review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished desktop-parity-2
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer desktop-parity-2` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed desktop-parity-2
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize desktop-parity-2
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/desktop-parity-2_finalized
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
scripts/orchestration/finalize desktop-parity-2
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/desktop-parity-2_finished
/tmp/wherewolf/desktop-parity-2_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
