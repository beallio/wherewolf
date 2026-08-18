# Plan: Catalog and editor persistence with history search (workspace-persistence)

## Context

Nothing the user builds up during a session survives closing the app. This plan covers
items 5, 6, and 8 from `feature-ideation-ui-quality-of-life.md`. It is the **second** of
three sequenced plans and assumes `ui-panel-polish` has already merged into `dev`;
branch from `dev` after that merge, not before.

### Defect A — the catalog does not persist

`src/wherewolf/services/catalog_service.py` has no save or load path, and
`src/wherewolf/storage/` contains only `history.py`. `SettingsService` persists window
geometry, splitter sizes, fonts, themes, export format, preview limit, and the last
dataset *directory* — but not the datasets themselves.

The consequence is that the product's core loop begins with re-adding the same files and
re-waiting for schema inspection and profiling, every single launch. It also produces a
concrete inconsistency: query history *does* persist
(`src/wherewolf/storage/history.py:13`, `~/.wherewolf/history.json`), so restoring a
query from history can hand the user SQL referencing aliases that no longer exist.

`CatalogService.__init__` already accepts `initial_entries: tuple[CatalogEntry, ...] | None`
(`:33`), so there is a clean injection seam — no restructuring required.

### Defect B — the query being written is lost on close

Only *executed* queries reach history (`main_window.py:614-620`). A draft the user was
halfway through — the interesting case, because it is the one that was not working yet —
is gone when the window closes. There is also no Open or Save action anywhere in
`DesktopActions` (`src/wherewolf/desktop/actions.py:15-24`), so there is no way to keep a
query as a file either. For a tool whose purpose is authoring SQL, the authored artifact
is the one thing it does not look after.

### Defect C — history cannot be searched

`HistoryDock` builds a `QTreeWidget` with sorting enabled (`history_dock.py:56-70`) but
no filter control. History is the product's memory, and by week three it is hundreds of
rows including every typo'd variant of every query. Sorting by timestamp does not help
you find "that join I got working on Tuesday". The 0.8.0 round already added
multi-select, delete, and save-as-SQL to this dock, so it is clearly meant to be worked
in; search is the missing half.

### Intended outcome

- The catalog is restored on launch. Entries whose file no longer exists are kept and
  shown as unavailable rather than dropped silently.
- The editor buffer survives a restart, and `.sql` files can be opened and saved.
- History can be filtered by substring and individual records can be pinned so they stop
  scrolling away.

### Design decisions already made

Settled with the user; do not revisit.

- **Storage mirrors `HistoryManager` exactly.** A new `CatalogStore` in
  `src/wherewolf/storage/catalog.py` writing `~/.wherewolf/catalog.json`, using the same
  atomic `tempfile.mkstemp` + `os.replace` pattern (`history.py:26-35`) and the same
  versioned-entry-with-migration shape. Do not invent a different mechanism, do not use
  `QSettings` for this, and do not add a database.
- **One catalog, not named workspaces.** A workspace switcher was considered and
  rejected for v1.
- **Missing files are flagged, not dropped.** A restored entry whose path no longer
  exists is kept in the catalog and rendered as unavailable.
- **Drafts and files are distinct surfaces.** Auto-restore of the buffer is separate
  from explicit Open/Save `.sql`. Both are in scope here. The named, parameterized
  saved-query library is item 12 and belongs to the `query-workspaces` plan — do not
  build it here.
- Only what the catalog needs to reconstruct an entry is persisted: `id`, `alias`,
  `path`, `source_format`. Schema and profile results are derived data and must be
  re-inspected on launch, never restored from disk.

**Slug used throughout this plan:** `workspace-persistence`

---

## Orchestration Contract

**Slug:** `workspace-persistence`

**Plan file:**

```text
docs/plans/2026-08-17_workspace-persistence.md
```

**Implementation branch:**

```text
feat/workspace-persistence
```

**Round-complete marker:**

```text
/tmp/wherewolf/workspace-persistence_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/workspace-persistence_finalized
```

**Review notes:**

```text
docs/review/workspace-persistence-review-*.md
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
git checkout -b feat/workspace-persistence
```

Commit this plan first:

```bash
git add docs/plans/2026-08-17_workspace-persistence.md
git commit -m "docs(plan): add workspace-persistence implementation plan"
```

---

## Implementation Tasks

Each task is **atomic**: one coherent behavior change, its own failing test first, its
own commit, independently verifiable. Do not batch two tasks into one commit. Run
`scripts/orchestration/run-quality-gates` before each commit.

Units are ordered A → B → C. Unit A's storage layer must be complete and committed
before the UI tasks that consume it.

### Unit A — Catalog persistence

**A1. `CatalogStore` — pure storage, no Qt.** *(one commit)*

Create `src/wherewolf/storage/catalog.py` modelled directly on
`src/wherewolf/storage/history.py`:

- `DEFAULT_PATH = Path.home() / ".wherewolf" / "catalog.json"`.
- `__init__(self, storage_path: Path | None = None)` with `_ensure_storage` creating the
  parent directory and an empty `[]` file.
- `save(entries: tuple[CatalogEntry, ...]) -> None` writing atomically via
  `tempfile.mkstemp` + `os.replace`, exactly as `_write_history` does at `history.py:26-35`.
  Persist only `id` (as `str`), `alias`, `path` (as `str`), and `source_format` (as its
  `.value`). Wrap the list in `{"version": 1, "entries": [...]}`.
- `load() -> tuple[CatalogEntry, ...]` reconstructing entries, skipping any record that
  is malformed rather than raising, and tolerating a bare top-level list as a
  pre-versioning shape.

This unit is pure Python with no Qt import. Test it directly in a new
`tests/test_catalog_store.py` against `tmp_path`: a round trip preserves alias, path and
format; a corrupt JSON file loads as empty rather than raising; a partially malformed
entry is skipped while good siblings survive; and — importantly — an interrupted write
leaves the previous good file intact (simulate by making the writer raise, then assert
the original content is still readable).

**A2. Mark unavailable entries in the domain model.** *(one commit)*

Add `unavailable: bool = False` to `CatalogEntry`
(`src/wherewolf/domain/models.py:42-54`). It is a frozen slots dataclass, so add the
field with its default at the end to keep positional construction working.

Do not infer unavailability by calling `Path.exists()` from the model or from the Qt
model's `data()` — a filesystem stat inside a paint path is a performance trap. It is
set once, at load time, in A3.

Test first: an entry defaults to `unavailable=False`, and `dataclasses.replace` can set
it to `True`.

**A3. Restore the catalog on launch.** *(one commit)*

In `src/wherewolf/desktop/main_window.py`, where `CatalogService()` is constructed,
load persisted entries via `CatalogStore` and pass them as `initial_entries`. For each
restored entry, stat its path **once** during load and set `unavailable=True` when it
does not exist.

Subscribe a listener to `CatalogService` that calls `CatalogStore.save(...)` whenever the
catalog changes — `subscribe` exists at `catalog_service.py:41`.

**`subscribe` cannot distinguish the change that caused the notification.**
`update_schema` (`:147`) and `update_profile` (`:177`) both call `_notify()`, exactly as
`add_paths` (`:86`), `rename` (`:114`) and `remove` (`:122`) do. A naive save-on-notify
therefore writes to disk on every background schema inspection and every profile
completion. Do not attempt to filter by inspecting the call stack.

Instead, make the listener **idempotent on the persisted projection**: build the
`(id, alias, path, source_format)` tuple list, compare it to the last one written, and
return without touching the disk when it is unchanged. Schema and profile updates do not
alter that projection, so they become no-ops naturally.

Test this explicitly: call `update_schema` on a restored catalog and assert the store's
write method was **not** called (spy on it or compare file mtime), then call `rename` and
assert it was. Without that assertion the redundant-write regression is invisible.

Accept an injectable store in `MainWindow.__init__` the same way `history_manager` is
injected at `:254`, so tests can point it at `tmp_path`.

Test first: construct a `MainWindow` with a store pre-seeded with two entries, one whose
file exists and one whose does not; assert both appear in the catalog, and that exactly
the missing one has `unavailable=True`. Then add a dataset and assert the store file on
disk now contains it — that second assertion is what proves the save subscription is
actually wired.

**A3b. Re-inspect restored entries.** *(one commit)*

Restoring entries into `CatalogService` puts rows in the table but does **not** schedule
the work that fills them in. `schema` and `profile` are deliberately not persisted (they
are derived), so without this task every restored row sits at `Loading` forever and the
schema panel and completion service have nothing to work with — the feature would look
implemented and be useless.

After restoration, dispatch the same schema-inspection path that `add_paths` triggers
today for each available entry. Find that path by reading how `main_window.py:764-770`
reacts to newly added datasets and reuse it rather than writing a second one. Honour the
existing `restore_profile_on_load` and `profile_max_bytes` settings (`:766-769`) so a
restored catalog does not profile gigabytes on launch.

Skip entries marked `unavailable` — do not schedule work against a path that is not
there.

Test first: restore two available entries and one unavailable one, and assert schema
inspection was requested for exactly the two available ones. Assert nothing was requested
for the unavailable entry.

**A4. Show unavailable entries in the catalog table.** *(one commit)*

In `src/wherewolf/desktop/models/catalog_model.py`, when `entry.unavailable` is true,
return `"Unavailable — file not found"` from the Schema status column (index 4) and a
dimmed foreground via `Qt.ItemDataRole.ForegroundRole` for that row. Reuse `dim_colour`
from `src/wherewolf/desktop/widgets/folder_column_delegate.py` rather than writing a
second blend function.

Test first: a model containing one available and one unavailable entry reports the
unavailable text for the right row only, and returns a `ForegroundRole` brush for the
unavailable row and `None` for the available one.

### Unit B — Editor drafts and `.sql` files

**B1. Persist and restore the editor buffer.** *(one commit)*

Add a `_editor_text_key` to `src/wherewolf/services/settings_service.py` following the
existing pattern at `:43-103` (`f"{schema_version}/editor/text"`), with
`save_editor_text` / `restore_editor_text` accessors defaulting to `""`.

Save the buffer in `MainWindow.closeEvent` and restore it during `_restore_state`
(`main_window.py:278`). Do not overwrite a restored draft with the
`SELECT * FROM <alias>` convenience text at `:760-761`; that branch already guards on
`not self.editor.text().strip()`, so restore must happen before any dataset is added.

Test first: set editor text, trigger the close path, construct a new `MainWindow`
against the same `QSettings`, and assert the text came back. Then assert that a restored
non-empty draft is **not** clobbered when a dataset is subsequently added.

**B2. Open and Save `.sql` files.** *(one commit)*

Add `open_sql`, `save_sql`, and `save_sql_as` to `DesktopActions`
(`src/wherewolf/desktop/actions.py`) with `QKeySequence.StandardKey.Open` already taken
by `add_datasets` — use `Ctrl+Shift+O` for Open SQL, `StandardKey.Save` for Save, and
`StandardKey.SaveAs` for Save As. Wire them into the File menu.

Track the current file path on `MainWindow` (`self._current_sql_path: Path | None`).
Save writes the editor buffer; Save with no current path falls through to Save As.

`src/wherewolf/desktop/dialogs/file_dialog_service.py` exposes only
`choose_dataset_files`, `choose_export_path`, and `choose_history_sql_path` (`:26-124`) —
there is **no** SQL open/save contract, so you must add one. Add
`choose_sql_open_path(default_directory, parent=None) -> Path | None` and
`choose_sql_save_path(default_directory, parent=None) -> Path | None` to **all three** of
`FileDialogService` (the `Protocol` at `:25`), `FakeFileDialogService` (`:35`), and
`QtFileDialogService` (`:62`). Adding to the Protocol without the Fake will break every
test that injects it.

`normalise_sql_destination` already exists at `:19` — use it for the save path so the
`.sql` extension is applied consistently. Do not call `QFileDialog` directly.

Show the current filename in the window title alongside the version
(`main_window.py:258`), and mark it dirty when the buffer differs from what was last
saved.

Test first: save the buffer to `tmp_path`, assert file contents match; open a different
`.sql` file and assert the buffer and the window title both updated; assert Save with no
current path routes to the Save As dialog.

### Unit C — History search and pinning

**C1. Filter the history list.** *(one commit)*

Add a `QLineEdit` (`self.history_filter`, `setObjectName("history_filter")`, placeholder
`Filter history`) above `self.history_table` in
`src/wherewolf/desktop/widgets/history_dock.py`. On `textChanged`, hide top-level items
whose query text does not contain the filter, case-insensitively, via
`item.setHidden(...)`.

Re-apply the filter at the end of `refresh()` (`:86-101`), which clears and rebuilds the
tree — otherwise a filter typed before a refresh silently stops applying.

Test first: populate several records, filter to a substring matching one, assert exactly
the matching items are unhidden. Then call `refresh()` and assert the filter still
applies — that is the assertion that catches the rebuild path.

**C2. Pin history records.** *(one commit)*

Add `pinned: bool` to history entries in `src/wherewolf/storage/history.py`. The file
already has a versioned-entry migration path (`_migrate_v1_entry`, `_is_v2_entry`,
`_is_v1_entry` at `:39-75`) — follow it: treat a v2 entry without `pinned` as
`pinned=False` rather than discarding it. Add `set_pinned(entry_id: str, pinned: bool)`.

**Pinned records must survive the history cap.** `add_entry` truncates with
`history = history[:100]` (`history.py:104`). As written, pinning a query and then
running 100 more would silently evict the pinned one — the feature failing at exactly the
moment it matters. Change the truncation to retain **all** pinned entries plus the most
recent unpinned entries up to the cap, rather than slicing the combined list blindly.

Decide and record in the session log what happens if pinned entries alone exceed the cap
(suggested: keep them all and let the cap apply only to unpinned entries; a user who pins
120 things meant to).

Test this specifically: pin one entry, add 150 more, and assert the pinned entry is still
present. That test fails against a naive `[:100]` slice.

In the dock, add a context-menu toggle `Pin` / `Unpin`, render pinned rows with a
leading marker, and sort pinned records above unpinned ones regardless of the active
sort column.

Test first, in `tests/test_history.py`: a legacy entry without `pinned` loads with
`pinned=False` and is not dropped; `set_pinned` round-trips through the file. Then in
`tests/test_history_dock.py`: pinned records appear above unpinned ones after a refresh.

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

Every step must be able to fail. Before adding a step of your own, answer: *what state
of the world makes this print the failure output?* If the answer is "none" or "only if
the tool is broken", it is decoration — delete it. Report actual output, not conclusions.

```bash
export QT_QPA_PLATFORM=offscreen
set -o pipefail
```

**`set -o pipefail` is mandatory for every step in this section.** Without it,
`pytest ... | tail` reports `tail`'s exit status and a failing suite is indistinguishable
from a passing one. Set it again in any fresh shell.

**Never point a test at the real `~/.wherewolf/`.** Every persistence test must inject a
`tmp_path`-based store or `QSettings`. A test that writes to the developer's real history
or catalog is a defect in the test, not a passing check.

### V1 — Baseline

```bash
./run.sh uv run pytest -q; echo "pytest exit=$?"
```

Record the tally and the exit code before any change.

### V2 — Prove nothing touches the real home directory

This runs early because it protects every later step. It must **fail closed**: a naive
`md5sum ~/.wherewolf/*.json` prints nothing when the directory is absent, so comparing
"nothing" to "nothing" passes even if the suite later creates the directory. Snapshot the
full state, including absence, and detect creation as well as modification:

```bash
snapshot () {
  if [ -d ~/.wherewolf ]; then
    find ~/.wherewolf -type f -print0 | sort -z | xargs -0r md5sum
  else
    echo "ABSENT"
  fi
}

snapshot > /tmp/wherewolf/home-before.txt
./run.sh uv run pytest -q; echo "pytest exit=$?"
snapshot > /tmp/wherewolf/home-after.txt

if diff -u /tmp/wherewolf/home-before.txt /tmp/wherewolf/home-after.txt; then
  echo "HOME UNCHANGED (before/after state shown above, including the ABSENT case)"
else
  echo "FAIL: a test wrote to the real ~/.wherewolf — diff above names the file"
  exit 1
fi
```

Print both snapshot files in your report, not just the verdict. `ABSENT` on both sides is
a legitimate pass; `ABSENT` before and a file list after is the exact failure this step
exists to catch. If any file changed or appeared, find the offending test and fix it
before continuing.

### V3 — Per-unit suites

```bash
./run.sh uv run pytest tests/test_catalog_store.py tests/test_catalog_model.py -q;  echo "A exit=$?"
./run.sh uv run pytest tests/test_main_window.py tests/test_settings_service.py -q; echo "B exit=$?"
./run.sh uv run pytest tests/test_history.py tests/test_history_dock.py -q;         echo "C exit=$?"
```

### V4 — Prove the round trip end to end

The unit tests exercise the store and the window separately. This proves they meet:

```bash
./run.sh uv run pytest tests/test_main_window.py -q -k "persist or restore" -v; echo "exit=$?"
```

There must be a test that builds a `MainWindow` against a `tmp_path` store, adds a
dataset, disposes of the window, builds a **second** `MainWindow` against the same store,
and asserts the dataset is present. A test that only checks `CatalogStore.save` wrote a
file does not prove restoration works.

### V5 — Prove the legacy history migration does not drop data

C2 changes the on-disk history shape. Run this directly and record the output:

```bash
./run.sh uv run pytest tests/test_history.py -q -k "migrat or legacy or pinned" -v; echo "exit=$?"
```

A v1 and a v2-without-`pinned` entry must both survive a load. Silently dropping
unrecognised entries would destroy a user's real history on upgrade, and it would look
like a passing test suite.

### V6 — Mutation gates (negative controls)

After V1–V5. Apply, run the suite, record it going **red**, revert, confirm green.

| # | Mutation | Suite that must go red |
|---|---|---|
| 1 | In `catalog.py`, make `save` a no-op | `tests/test_catalog_store.py`, `tests/test_main_window.py` |
| 2 | In `catalog.py`, let `load` raise on malformed JSON instead of returning empty | `tests/test_catalog_store.py` |
| 3 | In `main_window.py`, drop the `CatalogService.subscribe` save wiring | `tests/test_main_window.py` |
| 4 | In `main_window.py`, skip the `unavailable` stat at load so it is always `False` | `tests/test_main_window.py` |
| 5 | In `main_window.py`, stop restoring editor text in `_restore_state` | `tests/test_main_window.py` |
| 6 | In `history_dock.py`, skip re-applying the filter at the end of `refresh()` | `tests/test_history_dock.py` |
| 7 | In `history.py`, treat a v2 entry without `pinned` as invalid and drop it | `tests/test_history.py` |
| 8 | In `history.py`, restore the blind `history = history[:100]` truncation | `tests/test_history.py` |
| 9 | In `main_window.py`, make the save listener write unconditionally on every notify | `tests/test_main_window.py` |
| 10 | In `main_window.py`, skip scheduling re-inspection for restored entries | `tests/test_main_window.py` |

Mutations 4, 6, 7, 8 and 10 exist because each is a silent failure: the feature still
appears to work in casual use while quietly losing information or leaving rows
permanently blank. Mutation 9 is the counterpart to A3's redundant-write assertion —
without it, nothing detects a disk write on every background inspection.

### V7 — Full gates

```bash
scripts/orchestration/run-quality-gates
git status --short
```

Record the ruff, ty and pytest tallies as printed.

### Deferred and unverified

- **No upgrade test against a real pre-existing `~/.wherewolf/history.json`.** Migration
  is tested against synthesised fixtures only. Before release, back up a real history
  file and open the app against a copy of it.
- **Concurrent writers are not tested.** Two Wherewolf instances running at once will
  both write `catalog.json`; last writer wins. Single-instance behavior is assumed and
  not enforced.
- **File-dialog interactions go through `FakeFileDialogService`** in B2, so a broken
  `QtFileDialogService` implementation would not be caught by the suite. The Qt
  implementation is the one path with no automated coverage; exercise Open and Save once
  by hand before release.
- **No Windows verification.** `Path.home()` and path round-tripping through JSON behave
  differently on Windows; all measurement here is Linux.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished workspace-persistence
```

This writes:

```text
/tmp/wherewolf/workspace-persistence_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer workspace-persistence`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/workspace-persistence-review-*.md
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
   scripts/orchestration/clear-finished workspace-persistence
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
   git add docs/review/workspace-persistence-review-*.md
   git commit -m "docs(review): record workspace-persistence review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished workspace-persistence
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer workspace-persistence` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed workspace-persistence
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize workspace-persistence
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/workspace-persistence_finalized
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
scripts/orchestration/finalize workspace-persistence
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/workspace-persistence_finished
/tmp/wherewolf/workspace-persistence_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
