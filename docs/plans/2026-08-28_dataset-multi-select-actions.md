# Plan: Dataset panel multi-selection batch actions (dataset-multi-select-actions)

## Context

Make the dataset panel's context-menu actions apply to the whole selection. This is item
**3b**, the last outstanding item of a five-item user report: *"User actions should apply to
multiple selection, e.g. selecting multiple datasets, then right clicking remove would remove
the selected datasets."* Items 1, 3a, 3c and 4 are already merged.

The panel is `CatalogDock` (`src/wherewolf/desktop/widgets/catalog_dock.py:31`), a `QTableView`
over `CatalogModel`. GUI is **PyQt6**, not PySide6.

### Current behaviour

The view is already `ExtendedSelection`, so a user *can* select several rows — but every one of
the seven actions resolves a single entry through `_selected_entry`
(`catalog_dock.py:172-185`), which reads `selectionModel().currentIndex()`. Measured: with rows
0 and 1 selected, Remove deletes one row.

`_resolve_context_target` (`catalog_dock.py:187-208`, added by the merged 3c work) already
anchors the menu on the right-clicked row and already uses
`selection_model.rowIntersectsSelection(index.row())`. Keep it; batch enumeration builds on it.

### Per-action policy — sourced from real tools, not taste

Multi-selection is a **per-action** decision, not a global switch. Two independent precedents:
VS Code passes an explicit `respectMultiSelection` flag per command
(`getContext(false)` for Rename, `getContext(true)` for Delete); DBeaver expresses the same
thing declaratively per handler in its plugin manifest. Adopt that shape.

| Action | Policy | Precedent |
| --- | --- | --- |
| Remove | full selection, batch, **one** persistence write | VS Code delete iterates the selection with `distinctParents` dedupe |
| Refresh Schema | full selection | no external precedent; consistent with Remove |
| Copy Alias | full selection, `\n`-joined, **unquoted** | VS Code `fileCommands.ts:231-243`; DBeaver `NavigatorHandlerCopyAbstract.java:84-140` |
| Copy File Path | full selection, `\n`-joined, **unquoted** | same |
| Insert Alias at Cursor | full selection, `", "`-joined | no external precedent; comma suits `FROM a, b` |
| Rename Alias | **disabled** when more than one row is selected | DBeaver `plugin.xml:509-520` `<count value="1"/>` |
| Reveal in File Manager | enabled only when the selection spans **exactly one** distinct parent folder; reveal that folder | DBeaver `plugin.xml:843-857` `<count value="1"/>`; Nautilus `list_len_is_one`; Dolphin has no multi reveal |

Notes on the two judgement calls:

- **Rename disabled, not silently-single.** Nautilus, Dolphin and Finder all open a batch-rename
  dialog; DBeaver disables. Only VS Code silently renames the focused item, and that is a wart —
  the menu gives no hint the other N-1 selections are ignored. Batch alias rename with
  find/replace is a legitimate future feature, not this plan. Apple's HIG and KDE HIG
  (`layout_and_nav.md`: *"contextually irrelevant items disabled rather than being hidden"*) both
  favour dimming over hiding.
- **Reveal gated on one folder.** VS Code iterates every resource, i.e. selecting twelve datasets
  opens twelve file-manager windows. That is the behaviour to avoid. Gating on a single distinct
  parent folder never opens more than one window yet still serves the common case (several files
  in one folder), which DBeaver's strict `count == 1` does not.

### Keep `SelectItems`; do not switch to `SelectRows`

`setSelectionBehavior(SelectItems)` and `setSelectionMode(ExtendedSelection)` are set at
`catalog_dock.py:68-69`. **Leave both exactly as they are.**

Every peer tool selects whole objects rather than cells, so `SelectRows` is arguably the better
affordance and was considered. It is deliberately **not** adopted here, for three reasons:

1. This plan's job is batch actions. Changing the selection model at the same time couples two
   changes and enlarges the blast radius.
2. `SelectRows` churns behaviour the merged 3c round just shipped and verified, and would make
   `rowIntersectsSelection` largely redundant.
3. It breaks `test_catalog_cell_selection_keeps_context_actions_on_the_clicked_entry`
   (`tests/test_catalog_dock.py:448-484`) at lines 475-476 — `assert len(selected_indexes) == 1`
   becomes 5. That test was written to fix a real prior bug; changing its mechanism for no
   functional gain is not justified here.

Switching is a cheap one-line follow-up if the cell-selection affordance proves annoying in use.
The user reported that *actions* ignore the selection, not that selection itself feels wrong.

### Row enumeration — `selectedRows()` does not work here

Measured under this view's configuration:

| Mode | body click row 1, col 1 | `selectionModel().selectedRows()` |
| --- | --- | --- |
| `SelectItems` (current) | 1 index selected, column 1 | **`[]`** — empty |
| `SelectRows` (rejected) | 5 indexes, columns 0-4 | `[1]` |

`QItemSelectionModel.selectedRows()` returns a row only when **every** column in it is selected,
so under `SelectItems` it is empty for any ordinary click and is **not** a usable row enumerator.

Enumerate rows as `sorted({index.row() for index in selection_model.selectedIndexes()})`.
`selectedIndexes()` yields one index per selected *cell*, so a vertical-header click on one row
yields five indexes and must de-duplicate to one row. An implementation that calls
`selectedRows()` will silently act on nothing.

### `CatalogService` needs a batch removal that notifies once

`CatalogService.remove(self, entry_id: UUID) -> bool` (`services/catalog_service.py:116-123`)
calls `_notify()` (`:239-241`) on every successful removal. `MainWindow` subscribes
`_persist_catalog` at `main_window.py:380`, and `_persist_catalog` (`:2275-2287`) calls
`CatalogStore.save(entries)` (`storage/catalog.py:28-40`), which rewrites the whole file
atomically. So **N single removals cause N full-file writes.**

Add `remove_many` that filters once by a set of ids, assigns once, and calls `_notify()` exactly
once — and only if at least one id matched. Do **not** loop `remove()`. `add_paths` already
returns a `CatalogServiceReport` (`catalog_service.py:49`), so a batch-result return type has
precedent if one is wanted.

### Refresh Schema fan-out is pre-existing, and out of scope

`_queue_schema_work` (`main_window.py:1589-1600`) constructs a `SchemaWorker`, appends it to
`_schema_workers` (initialised `:402`) and calls `worker.start()` immediately. There is **no
queue and no cap**; the list is only bookkeeping for `closeEvent` (`:2381-2385`).

Refreshing N selected datasets therefore starts N threads. That is **not a new problem**: two
existing paths already do exactly this — `_queue_restored_catalog_work` (`:1568-1571`) loops
every restored entry on startup, and the add-datasets path (`:1544-1545`) loops `result.added`.
A user restoring twenty datasets already spawns twenty workers today.

So emit one `refresh_schema_requested` signal per selected entry and accept the existing
behaviour. **Do not** add a worker pool, queue or cap in this plan — capping schema work is a
real but separate concern that would also change startup, and belongs in its own plan.

### Non-goals

- No change to `setSelectionBehavior`/`setSelectionMode` (`catalog_dock.py:68-69`).
- No change to `_resolve_context_target`'s anchoring logic or its use of
  `rowIntersectsSelection`.
- No batch alias rename dialog.
- No schema-worker queue, pool or cap.
- No confirmation dialog on batch Remove. Removal only unregisters a dataset — nothing is
  deleted from disk. Both the GNOME and KDE HIGs prefer *undo* over confirmation for destructive
  removal, and undo for catalog mutations is a separate feature; a modal on every multi-remove is
  friction neither HIG asks for.
- No typed clipboard flavours. DBeaver attaches `TreeNode`/`DatabaseObject`/`FileTransfer`
  alongside the text; this stays text-only, since `FileTransfer` would make dataset rows
  drag-droppable as files, which is not wanted.
- Items 1, 2, 3a, 3c, 4 and 5 of the original report are not in this plan.

**Slug used throughout this plan:** `dataset-multi-select-actions`

---

## Orchestration Contract

**Slug:** `dataset-multi-select-actions`

**Plan file:**

```text
docs/plans/2026-08-28_dataset-multi-select-actions.md
```

**Implementation branch:**

```text
feat/dataset-multi-select-actions
```

**Round-complete marker:**

```text
/tmp/wherewolf/dataset-multi-select-actions_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/dataset-multi-select-actions_finalized
```

**Review notes:**

```text
docs/review/dataset-multi-select-actions-review-*.md
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
git checkout -b feat/dataset-multi-select-actions
```

Commit this plan first:

```bash
git add docs/plans/2026-08-28_dataset-multi-select-actions.md
git commit -m "docs(plan): add dataset-multi-select-actions implementation plan"
```

---

## Implementation Tasks

Work in order. All commands run from the repository root through the wrapper, e.g.
`./run.sh uv run pytest tests/test_catalog_dock.py`. Follow Red-Green-Refactor: write the failing
test first and record the observed failure before the production change. Commit atomically with
Conventional Commits.

Build bottom-up: service layer, then row enumeration, then per-action policies, then menu
enablement. `tests/test_catalog_dock.py` currently collects **24** tests.

### Task 1 (RED) — failing tests for `CatalogService.remove_many`

Add to `tests/test_catalog_service.py`, following its existing style:

1. `test_remove_many_removes_every_matching_entry` — three entries, remove two by id, assert the
   remaining tuple is exactly the third.
2. `test_remove_many_notifies_exactly_once` — subscribe a counter via
   `service.subscribe(...)` (`catalog_service.py:41-42`), remove two ids in one call, assert the
   listener fired **once**. This is the whole point of the method; without it, batch removal
   causes one full-file `CatalogStore.save` per dataset.
3. `test_remove_many_ignores_unknown_ids_without_notifying` — call with only unknown ids; assert
   entries unchanged and the listener fired **zero** times.
4. `test_remove_many_with_an_empty_iterable_does_nothing` — no change, no notification.
5. `test_remove_many_preserves_the_order_of_surviving_entries` — five entries, remove the second
   and fourth, assert the survivors keep their original relative order.

Run `./run.sh uv run pytest tests/test_catalog_service.py -q` and record the failure.

### Task 2 (GREEN) — `remove_many`

In `src/wherewolf/services/catalog_service.py`, add next to `remove` (`:116-123`):

```python
    def remove_many(self, entry_ids: Iterable[UUID]) -> tuple[UUID, ...]:
        """Remove every matching entry, notifying listeners at most once."""
```

Requirements:

- Materialise `entry_ids` into a `set` once — the caller may pass a generator, and it must not be
  consumed twice.
- Filter `self._entries` **once** and assign once.
- Call `self._notify()` exactly once, and only if at least one id matched.
- Return the ids actually removed, so a caller can report accurately.
- Do **not** implement it by looping `self.remove(...)`; that reintroduces N notifications.
- Leave `remove` unchanged — it is still used by the single-selection path and by existing tests.

Import `Iterable` from `collections.abc` if not already imported.

Run and record; all five new tests pass and every pre-existing `test_catalog_service.py` test
still passes.

Commit: `feat(catalog): add a batch removal that notifies once`.

### Task 3 (RED) — failing tests for row enumeration and batch actions

Add to `tests/test_catalog_dock.py`. Seed at least four datasets. Use
`monkeypatch.setattr(QMenu, "popup", lambda self, pos: None)` when invoking `_on_context_menu`,
as the existing 3c tests do.

**Selection helper:**

6. `test_catalog_selected_rows_dedupes_cells_from_the_same_row` — select three individual cells
   in row 1 (different columns) plus one cell in row 3; assert the dock's row-enumeration helper
   returns exactly `[1, 3]`. This pins the de-duplication that `selectedRows()` cannot do.

**Batch actions:**

7. `test_catalog_remove_deletes_every_selected_dataset` — select rows 0 and 2 (one cell each),
   trigger Remove, assert exactly the other two entries survive, by alias.
8. `test_catalog_remove_persists_once_for_a_batch` — subscribe a counter to the service, select
   three rows, trigger Remove, assert the listener fired **once**. This is the observable proof
   that `remove_many` is actually being used rather than a loop over `remove`.
9. `test_catalog_copy_alias_joins_selected_aliases_with_newlines` — select rows 0 and 2, trigger
   Copy Alias, assert the clipboard text equals `f"{alias0}\n{alias2}"` exactly — no quoting, no
   trailing newline.
10. `test_catalog_copy_path_joins_selected_paths_with_newlines` — same shape with `str(path)`.
11. `test_catalog_copy_uses_view_row_order_not_click_order` — select row 2 first, then row 0;
    assert the clipboard is still `alias0` then `alias2`. Clipboard order must follow the view,
    not the order the user happened to click.
12. `test_catalog_insert_alias_joins_selected_aliases_with_commas` — connect a `QSignalSpy` to
    `insert_alias_requested`, select rows 0 and 2, trigger Insert Alias, assert **one** signal
    carrying `f"{alias0}, {alias2}"`. One joined signal, not N signals.
13. `test_catalog_refresh_schema_emits_one_binding_per_selected_dataset` — spy on
    `refresh_schema_requested`, select three rows, trigger Refresh Schema, assert three
    emissions whose `entry_id`s match the selected rows.

**Gated actions:**

14. `test_catalog_rename_is_disabled_for_a_multi_row_selection` — select two rows, invoke
    `_on_context_menu` on one of them, assert `dock._rename_action.isEnabled() is False` while
    Remove, Refresh Schema, Copy Alias, Copy File Path and Insert Alias are all `True`.
15. `test_catalog_rename_stays_enabled_for_a_single_row` — one row selected; assert
    `_rename_action.isEnabled() is True`.
16. `test_catalog_reveal_is_enabled_for_several_files_in_one_folder` — seed datasets that share a
    parent directory, select two, invoke the menu, assert `_reveal_action.isEnabled() is True`.
17. `test_catalog_reveal_is_disabled_when_the_selection_spans_folders` — seed two datasets in
    **different** `tmp_path` subdirectories, select both, assert
    `_reveal_action.isEnabled() is False`.
18. `test_catalog_reveal_opens_one_target_for_several_files_in_one_folder` — monkeypatch
    `subprocess.Popen` in the `catalog_dock` module namespace to record calls; select two files in
    one folder, trigger Reveal, assert `Popen` was called **exactly once**. This is the assertion
    that prevents the VS Code behaviour of opening one window per file.

Run `./run.sh uv run pytest tests/test_catalog_dock.py -q` and record which fail. Expected: 6-18
all fail. If any passes before Task 4, stop and report — the premise is wrong.

### Task 4 (GREEN) — batch handlers in `CatalogDock`

In `src/wherewolf/desktop/widgets/catalog_dock.py`:

**Add a row-enumeration helper** next to `_selected_entry` (`:172-185`):

```python
    def _selected_entries(self) -> tuple[tuple[CatalogEntry, int], ...]:
        """Return every selected dataset in view row order, de-duplicated by row."""
        selection_model = self._view.selectionModel()
        if selection_model is None:
            return ()
        row_count = self._model.rowCount()
        rows = sorted(
            {
                index.row()
                for index in selection_model.selectedIndexes()
                if 0 <= index.row() < row_count
            }
        )
        return tuple((self._model.entry_at(row), row) for row in rows)
```

Do **not** use `selectionModel().selectedRows()` — measured empty under `SelectItems`.
Leave `_selected_entry` and `_resolve_context_target` unchanged; Rename still uses
`_selected_entry`.

**Rewrite these handlers to iterate `_selected_entries()`:**

- `_remove_selected` (`:258-264`) — collect `entry.id` for every selected row and make **one**
  `self._catalog_service.remove_many(ids)` call.
- `_refresh_schema` (`:266-278`) — emit one `refresh_schema_requested` per selected entry,
  preserving the existing `CatalogBinding(...)` construction.
- `_copy_alias` (`:281-288`) — `"\n".join(entry.alias for entry, _ in selected)`.
- `_copy_path` (`:291-298`) — `"\n".join(str(entry.path) for entry, _ in selected)`.
- `_insert_alias` (`:317-322`) — emit **one** `insert_alias_requested` with
  `", ".join(entry.alias for entry, _ in selected)`.
- `_reveal_selected` (`:310-315`) — compute `{entry.path.parent for entry, _ in selected}`. If
  that set does not have exactly one element, return without doing anything. Otherwise make one
  `subprocess.Popen(self.reveal_command(target))` call. `reveal_command` is at `:300-307`;
  `tests/test_main_window.py:2793` asserts it accepts either the file or its parent
  (`assert str(source.parent) in command or str(source) in command`), so passing a directory is
  already supported — but confirm by reading it before choosing what to pass.

Leave `_rename_selected_alias` (`:237-256`) **unchanged**.

Each handler must be a no-op on an empty selection, exactly as today.

Run and record; tests 6-13 and 16-18 pass.

Commit: `feat(catalog): apply dataset actions to the whole selection`.

### Task 5 (GREEN) — per-action menu enablement

`_on_context_menu` (`:210-235`) currently enables all seven actions on the single condition
`selection is not None`. Replace that with the per-action policy:

```python
        target = self._resolve_context_target(position)
        selected = self._selected_entries() if target is not None else ()
        has_any = bool(selected)
        single = len(selected) == 1
        one_folder = len({entry.path.parent for entry, _ in selected}) == 1

        self._rename_action.setEnabled(single)
        self._remove_action.setEnabled(has_any)
        self._refresh_action.setEnabled(has_any)
        self._copy_alias_action.setEnabled(has_any)
        self._copy_path_action.setEnabled(has_any)
        self._insert_alias_action.setEnabled(has_any)
        self._reveal_action.setEnabled(has_any and one_folder)
```

Keep the existing menu assembly and `popup` call (`:222-235`) untouched, and keep calling
`_resolve_context_target` **first** so the 3c anchoring still runs before enablement is computed.
A blank-space right-click must still disable all seven — that is what the `target is not None`
guard preserves, and `tests/test_catalog_dock.py:249-260` asserts it.

Run and record; tests 14-15 pass and the four existing 3c right-click tests
(`tests/test_catalog_dock.py:131-260`) still pass.

Commit: `feat(catalog): gate rename and reveal by selection shape`.

### Task 6 — documentation and session log

- Add a `### Changed` entry under `## Unreleased` in `CHANGELOG.md`, in the user-visible prose
  style of the released sections. State that dataset actions now apply to every selected dataset;
  that copies are one value per line; that Insert Alias inserts a comma-separated list; that
  Rename is unavailable with more than one selected; and that Reveal requires the selection to be
  in a single folder.
- Update `README.md` only if it documents the dataset panel; check first.
- Write the session log required by `AGENTS.md` §14 to
  `docs/agent_conversations/2026-08-28_dataset-multi-select-actions.json`: date, objective, files
  modified (**including this plan file**), tests added, design decisions — specifically why
  `remove_many` notifies once rather than looping `remove`, why `selectedRows()` is unusable under
  `SelectItems`, why Rename is disabled rather than acting on the anchor, why Reveal is gated on a
  single folder, and why `SelectItems` was retained — and results. List every commit sha you
  created.

Commit: `docs: record dataset-multi-select-actions changes`.

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

Run after the Quality Gates above pass. Every step must be able to fail; see
`references/verification-standards.md`. Record **actual output** — tallies, failing test names,
observed values — never a bare conclusion.

### V1 — mutation: prove batch removal really is batched

Temporarily reimplement `_remove_selected` as a loop:
`for entry, _ in self._selected_entries(): self._catalog_service.remove(entry.id)`.

```bash
./run.sh uv run pytest tests/test_catalog_dock.py -q -k "remove"
```

Expected failure: `test_catalog_remove_persists_once_for_a_batch` fails, reporting 3
notifications where 1 was expected, while
`test_catalog_remove_deletes_every_selected_dataset` still **passes** — because the loop is
functionally correct but causes N full-file writes. That contrast is the point: record both
outcomes. If the persist-once test also passes, it is not observing the listener; fix it before
continuing. Restore.

### V2 — mutation: prove row de-duplication is load-bearing

Temporarily change `_selected_entries` to use
`selection_model.selectedRows()` instead of the de-duplicated `selectedIndexes()` comprehension.

Expected failure: because `selectedRows()` is empty under `SelectItems`, **every** batch test
(7-13) fails with an empty selection, and
`test_catalog_selected_rows_dedupes_cells_from_the_same_row` fails returning `[]`. Record the
count of failures. Then, separately, drop only the `set(...)` de-duplication (keep
`selectedIndexes()`), and confirm
`test_catalog_selected_rows_dedupes_cells_from_the_same_row` fails with row 1 repeated. Two
distinct mutations, two recorded results. Restore.

### V3 — mutation: prove the enablement gates

Three separate mutations, each run and recorded:

1. `self._rename_action.setEnabled(has_any)` instead of `single` → expected failure:
   `test_catalog_rename_is_disabled_for_a_multi_row_selection`.
2. `self._reveal_action.setEnabled(has_any)` instead of `has_any and one_folder` → expected
   failure: `test_catalog_reveal_is_disabled_when_the_selection_spans_folders`.
3. In `_reveal_selected`, drop the single-folder guard and loop
   `Popen` over every selected entry (the VS Code behaviour) → expected failure:
   `test_catalog_reveal_opens_one_target_for_several_files_in_one_folder`, reporting 2 `Popen`
   calls where 1 was expected.

Restore all three.

### V4 — negative control: full suite

Runs **after** V1-V3 so it cannot pass merely because nothing was exercised. Run each command
separately; do not chain with `&&` and do not pipe, so no failure is masked:

```bash
./run.sh uv run ruff check .
./run.sh uv run ruff format --check .
./run.sh uv run ty check src/
./run.sh uv run pytest
```

Record each exit status and the pytest pass/fail/skip tallies. The suite was **965 passed, 9
deselected** before this plan; report the new totals and account for the difference by the number
of tests you added. Confirm `tests/test_catalog_dock.py` grew from **24**; state the new count.

Confirm explicitly that these four pre-existing tests still pass unchanged, since they are the
ones most exposed to this change:

- `test_catalog_cell_selection_keeps_context_actions_on_the_clicked_entry` (`:448-484`)
- `test_catalog_vertical_header_click_selects_the_whole_row` (`:487-522`)
- `test_catalog_context_menu_copy_and_remove_actions` (`:424-445`)
- `test_catalog_right_click_on_blank_space_disables_every_context_action` (`:222-260`)

If any of them needed editing, stop and report rather than editing — the plan expects all four to
pass untouched, and a failure means the design was misapplied.

### V5 — observed-value check on clipboard and reveal

Print real values rather than asserting booleans. In a scratch script under `/tmp/wherewolf/`
(do not commit it), build a `CatalogDock` with four datasets — three in one folder, one in a
second folder — then print:

1. the enumerated rows for a mixed cell selection;
2. the exact clipboard text for Copy Alias and Copy File Path with two rows selected, using
   `repr()` so newlines are visible;
3. the enabled state of all seven actions for: one row selected, two rows in one folder, two rows
   across two folders, and a blank-space click.

Paste the printed output into the session log, then delete the script.

### Deferred and unverified

State these explicitly in the session log; do not claim them as verified:

- **On-screen confirmation is deferred.** Everything runs under `QT_QPA_PLATFORM=offscreen`
  (`tests/conftest.py:14`). That proves selection enumeration, clipboard contents, signal
  payloads and action enablement, but not that greyed-out Rename/Reveal *look* correct, nor that a
  real file manager opens once. The user must confirm on a windowed session via
  `./run.sh uv run wherewolf-desktop`: Ctrl-click several datasets, check Rename is greyed, Remove
  removes all, Copy pastes one per line, and Reveal opens exactly one window.
- **Schema-worker fan-out is unchanged and uncapped.** Refreshing N datasets starts N threads,
  matching what startup and add-datasets already do. No test asserts a thread ceiling. Capping is
  a separate plan.
- **`SelectItems` retained.** Selecting several datasets still means selecting cells, so the
  visual affordance is cell-based even though actions are row-based. Switching to `SelectRows` is
  a one-line follow-up if that proves annoying.
- **No undo for batch Remove.** Nothing is deleted from disk, but re-adding N datasets is N manual
  steps. Undo for catalog mutations is a separate feature.
- **Non-local paths.** Reveal is only meaningful for local filesystem paths; behaviour for any
  future non-local source is unspecified and untested.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished dataset-multi-select-actions
```

This writes:

```text
/tmp/wherewolf/dataset-multi-select-actions_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer dataset-multi-select-actions`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/dataset-multi-select-actions-review-*.md
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
   scripts/orchestration/clear-finished dataset-multi-select-actions
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
   git add docs/review/dataset-multi-select-actions-review-*.md
   git commit -m "docs(review): record dataset-multi-select-actions review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished dataset-multi-select-actions
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer dataset-multi-select-actions` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed dataset-multi-select-actions
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize dataset-multi-select-actions
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/dataset-multi-select-actions_finalized
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
scripts/orchestration/finalize dataset-multi-select-actions
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/dataset-multi-select-actions_finished
/tmp/wherewolf/dataset-multi-select-actions_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
