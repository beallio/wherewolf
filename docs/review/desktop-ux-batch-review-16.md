# Review — desktop-ux-batch (round 16)

Branch: `feat/desktop-ux-batch`
Reviewed against: `docs/plans/2026-08-11_desktop-ux-batch.md`
Commit reviewed: `7bb046e feat(history): save selected history records as SQL`

## Verdict

**Task 13 is NOT accepted.** The feature works and the architecture is right —
the dialog stays out of the widget, the write goes through `write_atomically`,
and cancellation writes nothing. But the plan's `.sql` suffix requirement is
**tested only against the fake's reimplementation of it**, so production's copy is
unprotected.

Do not advance to Task 14. Fix in place, re-run the gates, re-commit, re-mark.

## The defect

`FakeFileDialogService.choose_history_sql_path` and
`QtFileDialogService.choose_history_sql_path` each implement the suffix rule
separately. `test_main_window_saves_selected_history_records_as_sql` passes a
suffix-less `destination` and asserts the file lands at
`destination.with_suffix(".sql")` — but it is the **fake** that appends the
suffix on that path. Nothing exercises the production implementation.

Measured: deleting the suffix logic from `QtFileDialogService` **only**, leaving
the fake untouched:

```text
534 passed, 7 deselected
```

The whole suite stays green while the shipped behaviour is gone. A user typing
`myqueries` in the save dialog would get an extension-less file.

This is the second time on this branch that duplicated logic in a test double has
hidden production behaviour. Treat a fake that reimplements a rule as a signal to
extract the rule.

## Required changes

### MECHANICAL — extract the rule so the fake cannot drift

Add a module-level helper to
`src/wherewolf/desktop/dialogs/file_dialog_service.py` and call it from **both**
implementations:

```python
def normalise_sql_destination(destination: Path) -> Path:
    """Return the chosen history-SQL path with a .sql suffix when none was typed."""
    return destination if destination.suffix else destination.with_suffix(".sql")
```

In `FakeFileDialogService.choose_history_sql_path`:

```python
        if self.history_sql_path is None:
            return None
        return normalise_sql_destination(self.history_sql_path)
```

In `QtFileDialogService.choose_history_sql_path`:

```python
        if not name:
            return None
        return normalise_sql_destination(Path(name))
```

This mirrors how `normalise_destination` (`services/export_destination.py`)
already serves the export path for both services.

### MECHANICAL — test the production dialog wrapper directly

Add to `tests/test_file_dialog_service.py`, following the existing monkeypatch
precedent at `tests/test_file_dialog_service.py:113`:

```python
@pytest.mark.parametrize(
    ("chosen", "expected"),
    [("/tmp/history", "/tmp/history.sql"), ("/tmp/history.sql", "/tmp/history.sql"),
     ("/tmp/history.txt", "/tmp/history.txt")],
)
def test_qt_history_sql_path_appends_suffix(monkeypatch, chosen, expected):
    monkeypatch.setattr(
        "wherewolf.desktop.dialogs.file_dialog_service.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (chosen, ""),
    )
    assert QtFileDialogService().choose_history_sql_path(None) == Path(expected)


def test_qt_history_sql_path_cancellation_returns_none(monkeypatch):
    monkeypatch.setattr(
        "wherewolf.desktop.dialogs.file_dialog_service.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: ("", ""),
    )
    assert QtFileDialogService().choose_history_sql_path(None) is None
```

Note the third parameter case: an explicit non-`.sql` suffix must be **left
alone**, not rewritten.

Both the helper extraction and these tests were applied and measured by the
reviewer before being prescribed:

```text
proposed tests against the fixed implementation   -> 4 passed
proposed tests against the stripped implementation -> 1 failed (the suffix-less case)
```

The reviewer's tree was reverted; the patch is yours to apply.

## Not at issue

- Signal-out-of-widget design, `write_atomically`, `OSError` → `_show_status`,
  cancellation writing nothing, and the `getattr` capability probe matching the
  existing `choose_export_path` pattern are all correct.
- The action is disabled when nothing is selected, alongside Delete.

## Non-blocking observations

- `history_records_selected` reads like a selection-changed notification rather
  than a save request. `save_as_sql_requested` would say what it means. Rename
  only if you are touching that line anyway.
- `_save_history_records_as_sql` passes `None` as the dialog's default directory,
  so the save dialog opens wherever the process happens to be. The export flow
  threads a remembered directory through `choose_export_path`, and
  `SettingsService.restore_last_dataset_directory()` already exists. Out of scope
  for this task — note it in the session log.

STATUS: CHANGES_REQUESTED
