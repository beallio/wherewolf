# Plan: Completion list keyboard navigation and absolute paged row numbers (completion-keys-paged-row-numbers)

## Context

This plan fixes two independent, empirically verified desktop UI defects. Item numbers
follow the user's original five-item report; **items 2, 3 and 5 of that report are out of
scope here** and will be handled under separate plans.

The GUI is **PyQt6 + QScintilla**, not PySide6.

### Defect 1 — arrow keys close the intellisense completion list instead of navigating it

`SqlEditor` (`src/wherewolf/desktop/widgets/sql_editor.py:32`) subclasses `QsciScintilla`.
The completion popup is QScintilla's **native user list**, shown by
`CompletionAdapter.request_completion` via `SCI_USERLISTSHOW`
(`src/wherewolf/desktop/widgets/completion_adapter.py:105-115`). There is no `QCompleter`,
no custom popup widget, and no event filter anywhere in `src/`.

QScintilla's inherited `ScintillaBase::KeyCommand` already implements the whole active-list
key set: `Up`/`Down` move one entry, `PageUp`/`PageDown` move a page, `Home`/`End` jump to
first/last, `Tab` and `Return` accept the highlighted entry, `Escape` cancels. The
application destroys the list before QScintilla can act on it:

```python
# src/wherewolf/desktop/widgets/sql_editor.py:210-215
def keyPressEvent(self, e: QKeyEvent) -> None:
    """Return printable typing to the document before refreshing a user list."""

    if e.text().isprintable() and self.isListActive():
        self._completion_adapter.cancel()
    super().keyPressEvent(e)
```

**Root cause:** `"".isprintable()` returns `True` in Python — an empty string is printable by
definition. Arrow, page and Home/End keys all produce `QKeyEvent.text() == ""`, so the gate
fires, `CompletionAdapter.cancel()` sends `SCI_AUTOCCANCEL`, and by the time
`super().keyPressEvent(e)` reaches `ScintillaBase::KeyCommand` there is no list left to
navigate. `Up`/`Down` then fall through to plain caret movement.

Measured against the real widget under `QT_QPA_PLATFORM=offscreen` (type `SELECT dt`, wait
for `isListActive()`, send one key):

| Key | `QKeyEvent.text()` | gate fires | behaviour today |
| --- | --- | --- | --- |
| `Down` | `""` | yes | **list closes** |
| `Up` | `""` | yes | **list closes** |
| `Tab` | `"\t"` | no | works — inserts `SELECT DATE_TRUNC(` |
| `Return` | `"\r"` | no | works — inserts `SELECT DATE_TRUNC(` |

`Tab` and `Return` acceptance already behave as the user expects and need **no new code**.
The user-visible effect of the bug is that intellisense is effectively top-suggestion-only.

**The fix is one condition: require non-empty text.** A key allow-list is *not* needed and
must not be added — every key QScintilla consumes for an active list yields either empty
text or a non-printable control character, so `text and text.isprintable()` already excludes
all of them. This was verified against the real widget with the one-condition change applied:

- `Down` moves the highlight `DATE_TRUNC` (index 0) → `EQUI_WIDTH_BINS` (index 1), list stays open.
- `Down`,`Down`,`Up` lands on index 1; `Tab` then inserts `SELECT EQUI_WIDTH_BINS(`.
- `End` jumps from index 0 to index 66 (`UPDATE`), list stays open.
- `Left` and `Right` still close the list — QScintilla cancels on caret movement by itself,
  so the application does not need to; this behaviour is preserved for free.
- `Escape` still cancels with the document unchanged (`SELECT dt`).
- `Return` still accepts (`SELECT DATE_TRUNC(`).
- Typing a printable character still refreshes the list (`SELECT dte`), which is the
  behaviour the original gate existed to protect.

Existing key-level coverage only ever presses `Return`
(`tests/test_sql_editor.py:632-647` and `:649-679`). There is no test for `Up`, `Down`,
`PageUp`, `PageDown`, `Home` or `End`, which is why this shipped.

### Defect 2 — paginated result row numbers restart at 1 on every page

Result row labels come from the results table's default vertical header, fed by:

```python
# src/wherewolf/desktop/models/polars_table_model.py:84-89
if (
    orientation == Qt.Orientation.Vertical
    and 0 <= section < self._frame.height
    and role == Qt.ItemDataRole.DisplayRole
):
    return section + 1
```

There is no page offset. Measured with a 1000-row page-2 frame loaded into
`ResultTableView`: first label `1`, last label `1000` (expected `1001` and `2000`).
`dir(PolarsTableModel())` contains no offset attribute or setter.

The offset genuinely exists upstream and is discarded:

- `PageWorker` computes `offset = self._page_index * request.preview_limit`
  (`src/wherewolf/desktop/page_controller.py:35-45`).
- `PageResult` carries `offset` and `page_size` (`src/wherewolf/domain/models.py:157-165`).
- `MainWindow` validates `result.offset` (`src/wherewolf/desktop/main_window.py:990-992`),
  then rebuilds a `QueryResult` and drops the offset.
- `_render_query_result` calls `self.result_table_view.set_frame(result.frame)`
  (`src/wherewolf/desktop/main_window.py:1244`), and
  `ResultTableView.set_frame(self, frame)` (`src/wherewolf/desktop/widgets/result_table_view.py:67`)
  accepts no offset.

The status label already computes the absolute range correctly and independently:
`start = state.page_index * request.preview_limit + 1`
(`src/wherewolf/desktop/main_window.py:2515`). So today the UI reads
`rows 1,001-2,000 · Page 2` while the row headers next to it read `1`-`1000`.

Two facts that constrain the fix, both measured rather than assumed:

1. **`TypedSortProxyModel` does not override `headerData`**, so
   `QSortFilterProxyModel::headerData` maps vertical sections straight through to the source
   model. The fix therefore belongs in `PolarsTableModel.headerData` and needs no proxy
   change. It also means a local sort keeps each label attached to its record — which matches
   the user's requirement that "row numbers track the numbers corresponding to records".
2. **The vertical header auto-widens for longer labels and needs no work.** Its resize mode is
   `Fixed` but `QHeaderView`'s vertical size hint is computed from section labels with
   `resizeContentsPrecision == 1000`; measured width grew 33 px → 54 px when 1000 labels went
   from 1-digit to 7-digit. Do not add header-width code.

There is exactly **one** render path to plumb. `_render_current_editor_result`
(`src/wherewolf/desktop/main_window.py:1300-1319`) either clears the view with
`set_frame(None)` or delegates to `_render_query_result` at line 1319, so tab switching
re-enters the same code path. Fixing `_render_query_result` covers first render, page
navigation, and tab switching.

### Non-goals

- No key allow-list, event filter, `QCompleter`, or custom popup for defect 1.
- No change to `Tab`/`Return`/`Escape`/`Left`/`Right` list behaviour — all already correct.
- No vertical-header width, delegate, or `setVerticalHeaderLabels` code for defect 2.
- No change to `TypedSortProxyModel`, `result_pagination.py`, `PageController`, `PageResult`,
  `RowCountController`, export paths, or the headless CLI.
- Items 2 (Saved SQL panel refresh/visibility), 3 (dataset column resizing and multi-select
  actions) and 5 (Edit ▸ Format Text) from the original report are **not** in this plan. If you
  spot related issues, record them in the session log for a separate plan.

**Slug used throughout this plan:** `completion-keys-paged-row-numbers`

---

## Orchestration Contract

**Slug:** `completion-keys-paged-row-numbers`

**Plan file:**

```text
docs/plans/2026-08-28_completion-keys-paged-row-numbers.md
```

**Implementation branch:**

```text
feat/completion-keys-paged-row-numbers
```

**Round-complete marker:**

```text
/tmp/wherewolf/completion-keys-paged-row-numbers_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/completion-keys-paged-row-numbers_finalized
```

**Review notes:**

```text
docs/review/completion-keys-paged-row-numbers-review-*.md
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
git checkout -b feat/completion-keys-paged-row-numbers
```

Commit this plan first:

```bash
git add docs/plans/2026-08-28_completion-keys-paged-row-numbers.md
git commit -m "docs(plan): add completion-keys-paged-row-numbers implementation plan"
```

---

## Implementation Tasks

Work the tasks in order. Every command runs from the repository root through the wrapper,
e.g. `./run.sh uv run pytest tests/test_sql_editor.py`. Follow Red-Green-Refactor: each
behaviour task writes its failing test **first**, and you must record the observed failure
before writing the production change.

Commit atomically — one coherent change per commit, Conventional Commits, pre-commit hooks
run before each commit.

### Task 1 (RED) — failing tests for completion-list keyboard navigation

Add to `tests/test_sql_editor.py`, next to the existing user-list tests at lines 632-679 and
following their harness exactly (`editor.show()`, `QTest.qWaitForWindowExposed(editor)`,
`editor.setFocus()`, `QTest.keyClicks(editor, "SELECT dt")`,
`qtbot.waitUntil(editor.isListActive)`).

Read the highlighted entry out of the active list with Scintilla messages, not by guessing:

```python
def _highlighted_entry(editor) -> tuple[int, str]:
    buffer = bytearray(256)
    length = editor.SendScintilla(editor.SCI_AUTOCGETCURRENTTEXT, 0, buffer)
    return editor.SendScintilla(editor.SCI_AUTOCGETCURRENT), bytes(buffer[:length]).decode()
```

Add these tests:

1. `test_sql_editor_arrow_down_moves_the_completion_highlight_without_closing_the_list` —
   after one `Qt.Key.Key_Down`, assert `editor.isListActive()` is still true **and** the
   highlighted index advanced from `0` to `1`.
2. `test_sql_editor_arrow_up_keeps_the_completion_list_open` — after one `Qt.Key.Key_Up`,
   assert `editor.isListActive()` is still true.
3. `test_sql_editor_arrow_down_then_tab_inserts_the_highlighted_completion` — send
   `Down`, capture the highlighted label, send `Qt.Key.Key_Tab`, then
   `qtbot.waitUntil` the document equals `f"SELECT {label}("` for a function entry. Do not
   hardcode a second function name: the completion catalog is generated, so derive the
   expected text from the label you captured.
4. `test_sql_editor_end_key_jumps_to_the_last_completion_entry` — after `Qt.Key.Key_End`,
   assert the list is still active and the highlighted index is greater than before.

Also add regression tests for the behaviour that must **not** change:

5. `test_sql_editor_caret_movement_keys_still_close_the_completion_list` — parametrise over
   `Qt.Key.Key_Left` and `Qt.Key.Key_Right`; assert `not editor.isListActive()` and the
   document is unchanged (`"SELECT dt"`).
6. `test_sql_editor_typing_a_printable_character_still_refreshes_the_completion_list` — send
   `"e"`, assert the document becomes `"SELECT dte"`.

Run `./run.sh uv run pytest tests/test_sql_editor.py -q` and record which tests fail.
Expected: tests 1, 2 and 4 fail; test 3 may fail; tests 5 and 6 pass. If tests 1, 2 or 4
pass at this point, stop — the premise of this plan is wrong; report it and do not proceed.

### Task 2 (GREEN) — require non-empty text before cancelling the list

Change **only** the gate in `SqlEditor.keyPressEvent`
(`src/wherewolf/desktop/widgets/sql_editor.py:210-215`):

```python
def keyPressEvent(self, e: QKeyEvent) -> None:
    """Return printable typing to the document before refreshing a user list.

    An empty ``QKeyEvent.text()`` is "printable" in Python, so the emptiness check is
    load-bearing: without it every arrow, page and Home/End key cancels the active user
    list before QScintilla can navigate or accept it.
    """

    text = e.text()
    if text and text.isprintable() and self.isListActive():
        self._completion_adapter.cancel()
    super().keyPressEvent(e)
```

Do not add a key set, `Qt.Key` comparison, event filter, or any other branch — the emptiness
check alone is sufficient and was verified as such. Do not touch `CompletionAdapter`.

Re-run `./run.sh uv run pytest tests/test_sql_editor.py -q` and record the tallies. All six
new tests and all pre-existing tests in the file must pass.

Commit: `fix(editor): keep the completion list open for keyboard navigation`.

### Task 3 (RED) — failing tests for absolute paged row labels

Add to `tests/test_polars_table_model.py`, following the existing
`test_polars_table_model_basic` style:

1. `test_polars_table_model_row_labels_include_the_page_row_offset` — build a 3-row frame with
   `row_offset=1000`; assert vertical `DisplayRole` labels for sections `0` and `2` are `1001`
   and `1003`.
2. `test_polars_table_model_row_labels_default_to_one_based_numbering` — no offset supplied;
   assert section `0` is `1`. This pins the existing contract so the default cannot regress.
3. `test_polars_table_model_rejects_a_negative_row_offset` — assert `ValueError`.

Add to `tests/test_result_table_view.py` (this file already exists — add to it, do not create
a new one):

4. `test_result_table_view_row_labels_track_the_page_offset` — call
   `view.set_frame(frame, row_offset=1000)` on a 1000-row frame and assert the **proxy** model
   (`view.model()`, not `view.source_model()`) reports vertical labels `1001` for section `0`
   and `2000` for section `999`. Asserting through the proxy proves the label survives
   `QSortFilterProxyModel`'s section mapping.

Add to `tests/test_main_window.py`, beside the existing pagination tests (from line 4591) and
reusing their harness for a truncated DuckDB preview:

5. `test_main_window_next_page_row_labels_continue_from_the_previous_page` — run a query that
   truncates, click Next, wait for the page to land, then assert the results view's proxy
   model reports a first vertical label of `preview_limit + 1`, and that it agrees with the
   `start` value already shown in `window.page_status_label.text()`.
6. `test_main_window_switching_tabs_preserves_paged_row_labels` — with a paged result on tab A,
   switch to another editor tab and back, then assert the first vertical label is still
   `preview_limit + 1`. This covers the `_render_current_editor_result` → `_render_query_result`
   re-render path, which is the easiest place for this fix to silently regress.

Run the three test files and record which tests fail. Expected: 1, 3, 4, 5 and 6 fail; 2
passes. If test 5 or 6 passes before Task 5 lands, stop and report it.

### Task 4 (GREEN) — carry a row offset on the results model and view

In `src/wherewolf/desktop/models/polars_table_model.py`:

- Add a `row_offset: int = 0` keyword argument to `__init__` and store `self._row_offset`.
- Add a keyword-only `row_offset: int = 0` parameter to
  `set_frame(self, frame: pl.DataFrame | None, *, row_offset: int = 0)` and assign it inside
  the existing `beginResetModel()` / `endResetModel()` block, so the frame and its labels
  change atomically and no header refresh signal is needed.
- Raise `ValueError` for a negative offset, matching the existing validation style of
  `SqlEditor.set_completion_dialect` (`src/wherewolf/desktop/widgets/sql_editor.py:147-153`).
- Change the vertical branch of `headerData` to `return section + self._row_offset + 1`.

In `src/wherewolf/desktop/widgets/result_table_view.py`:

- Change `set_frame(self, frame: pl.DataFrame | None)` to
  `set_frame(self, frame: pl.DataFrame | None, *, row_offset: int = 0)` and forward
  `row_offset` to `self._source_model.set_frame(...)`. Leave the rest of the method
  (header badges, auto-sizing, `frame_changed`) untouched.

The default of `0` keeps the two `set_frame(None)` call sites
(`src/wherewolf/desktop/main_window.py:1246` and `:1309`) and all existing tests working
unchanged. Do not touch `TypedSortProxyModel`.

Run the model and view test files; record tallies. Tests 1-4 from Task 3 must now pass.

Commit: `feat(results): carry a page row offset on the results table model`.

### Task 5 (GREEN) — plumb the page offset through MainWindow

In `src/wherewolf/desktop/main_window.py`, remove the duplicated offset arithmetic rather than
adding a second copy of it.

- Add one helper next to the paging code:

  ```python
  @staticmethod
  def _page_row_offset(state: _EditorTabState | None, request: ExecutionRequest) -> int:
      """Return the absolute row index of the first row of the state's current page."""
      if state is None:
          return 0
      return state.page_index * request.preview_limit
  ```

- In `_render_query_result` (line 1244), pass the offset:

  ```python
  if result.status is ExecutionStatus.SUCCEEDED and result.frame is not None:
      self.result_table_view.set_frame(
          result.frame,
          row_offset=self._page_row_offset(self._current_editor_state(), request),
      )
  else:
      self.result_table_view.set_frame(None)
  ```

- In `_update_page_controls`, replace line 2515
  (`start = state.page_index * request.preview_limit + 1`) with
  `start = self._page_row_offset(state, request) + 1`. Behaviour is identical; this keeps the
  two consumers of the offset from drifting apart again.

Do not change `_render_current_editor_result` — it already delegates to `_render_query_result`
at line 1319, so it is covered.

Run `./run.sh uv run pytest tests/test_main_window.py -q` and record tallies. Tests 5 and 6
from Task 3 must now pass, and the existing pagination tests from line 4591 must still pass.

Commit: `fix(results): number paged result rows from their absolute offset`.

### Task 6 — documentation and session log

- Add entries under the existing `## Unreleased` heading in `CHANGELOG.md`, following the
  prose style of the released sections (user-visible behaviour, not internals). Use a `### Fixed`
  subsection.
- Only touch `README.md` if it documents completion keys or result row numbering. Check first;
  do not add a section speculatively.
- Write the session log required by `AGENTS.md` §14 to
  `docs/agent_conversations/2026-08-28_completion-keys-paged-row-numbers.json`, including date,
  objective, files modified, tests added, design decisions (in particular: why no key allow-list
  was added, and why the offset lives on the model rather than the proxy), and results.

Commit: `docs: record completion-keys-paged-row-numbers changes`.

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

Run these after the Quality Gates above pass. Every step below must be able to fail; see
`references/verification-standards.md`. Record the **actual command output** — tallies,
failing test names, observed values — not a conclusion that it worked.

### V1 — mutation: prove the defect-1 gate is load-bearing

Temporarily revert the Task 2 change to `if e.text().isprintable() and self.isListActive():`
and run:

```bash
./run.sh uv run pytest tests/test_sql_editor.py -q -k "arrow or end_key"
```

Expected failure: at least
`test_sql_editor_arrow_down_moves_the_completion_highlight_without_closing_the_list` and
`test_sql_editor_arrow_up_keeps_the_completion_list_open` fail with the list reported inactive.
Record the failing test names and the assertion text. If every test still passes, the new tests
do not actually exercise the fix — fix the tests before continuing.

Restore the Task 2 change.

### V2 — mutation: prove the defect-2 offset is load-bearing

Temporarily change `PolarsTableModel.headerData`'s vertical branch back to `return section + 1`
and run:

```bash
./run.sh uv run pytest tests/test_polars_table_model.py tests/test_result_table_view.py -q
```

Expected failure: `test_polars_table_model_row_labels_include_the_page_row_offset` and
`test_result_table_view_row_labels_track_the_page_offset` fail, reporting `1` where `1001` was
expected. Record both failures.

Then, with `headerData` restored, temporarily revert only the Task 5 `_render_query_result`
change (drop the `row_offset=` argument) and run:

```bash
./run.sh uv run pytest tests/test_main_window.py -q -k "row_labels"
```

Expected failure: both Task 3 tests 5 and 6 fail. This separates "the model can carry an
offset" from "MainWindow actually supplies it" — a fix that only did the former would otherwise
look complete. Record the failures, then restore.

### V3 — negative control: full suite with both fixes in place

This step runs **after** V1 and V2 so it cannot pass merely because nothing was exercised.

```bash
./run.sh uv run ruff check .
./run.sh uv run ruff format --check .
./run.sh uv run ty check src/
./run.sh uv run pytest
```

Record the pytest pass/fail/skip tallies and the exit status of each command separately — do
not chain them with `&&` or pipe them, so a failure cannot be masked. Failure looks like a
non-zero exit from any of the four, or any test failure or error in the final tally. Note the
Spark tier is deselected by the default `-m 'not spark'` addopts; state the skip count.

### V4 — observed-value check on paged row labels

With the fixes in place, print the real numbers rather than asserting a boolean. In a scratch
script under `/tmp/wherewolf/` (do not commit it), load a 1000-row frame into a
`ResultTableView` with `row_offset=1000` and print the proxy model's vertical labels for
sections `0`, `1` and `999`.

Expected output: `1001`, `1002`, `2000`. Failure looks like `1`, `2`, `1000`. Paste the actual
printed values into the session log, then delete the script.

### Deferred and unverified

State these explicitly in the session log; do not claim them as verified:

- **On-screen visual confirmation is deferred.** All automated verification runs under
  `QT_QPA_PLATFORM=offscreen` (set by `tests/conftest.py:14`). That proves list state,
  highlighted index, document text and header labels, but it does **not** prove the popup's
  highlight bar and the vertical-header column render correctly on a real display. The user
  must confirm on a windowed session by launching `./run.sh uv run wherewolf-desktop`, typing a
  partial identifier, pressing `Down`/`Up`/`Tab`, then running a truncated query and clicking
  Next.
- **Vertical-header width was measured as self-correcting** (33 px → 54 px as labels grew) and
  is intentionally not covered by a test. If wider labels are ever clipped on a real display,
  that is a new defect, not a regression of this plan.
- **The Spark execution tier is not exercised.** Result paging is DuckDB-only, so Spark paths
  are untouched and untested here.
- **Non-DuckDB/multi-statement previews** cannot page (`_can_page_results`), so their row
  labels stay at offset `0` by construction; this is unchanged behaviour and not separately
  verified.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished completion-keys-paged-row-numbers
```

This writes:

```text
/tmp/wherewolf/completion-keys-paged-row-numbers_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer completion-keys-paged-row-numbers`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/completion-keys-paged-row-numbers-review-*.md
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
   scripts/orchestration/clear-finished completion-keys-paged-row-numbers
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
   git add docs/review/completion-keys-paged-row-numbers-review-*.md
   git commit -m "docs(review): record completion-keys-paged-row-numbers review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished completion-keys-paged-row-numbers
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer completion-keys-paged-row-numbers` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed completion-keys-paged-row-numbers
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize completion-keys-paged-row-numbers
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/completion-keys-paged-row-numbers_finalized
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
scripts/orchestration/finalize completion-keys-paged-row-numbers
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/completion-keys-paged-row-numbers_finished
/tmp/wherewolf/completion-keys-paged-row-numbers_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
