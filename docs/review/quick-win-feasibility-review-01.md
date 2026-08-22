# Quick-win feasibility review

Date: 2026-08-22
Scope: the four "Quick wins" in `feature-ideation-data-sources-and-workflow.md`, read against the
code at v0.10.1.

This document was fact-checked against the code by a second agent (codex, read-only) after the
first draft. Claims it disproved have been corrected in place; the disputed points are listed in
"Corrections after fact-check" at the end so the changes are auditable. One live defect was found
during that pass and is written up first, because it is worth more than any of the four features.

---

## Defect found during this review: copying a selection is wrong when a column is hidden

`ResultTableView.selection_for_export()` records each selected cell as
`(source_row, header.visualIndex(column))` (`widgets/result_table_view.py:104-124`) and returns
`column_order`, built from *non-hidden* logical columns sorted by visual index.
`serialize_to_tsv()` then resolves the model column as `column_order[v_col]`
(`clipboard_serializers.py:65`).

Those two indexings disagree. Qt's `visualIndex()` still counts hidden sections, but
`column_order` has had them removed, so every hidden column to the left of a selection shifts the
lookup by one and the copy silently returns a different column's data.

Verified empirically — three columns `a, b, c`, column `a` hidden, one cell selected in `b`
(value 2):

```
SELECTED_CELLS [(0, 1)]   COLUMN_ORDER [1, 2]   TSV '3'
```

The copy yields `3`, the value of `c`. Hiding a column is reachable from the results header
context menu, and this path backs both `Ctrl+C` and `Export Selection…`. The probe that
demonstrates it is at
``/tmp/claude-1000/-home-beallio-Dropbox-Scripts-wherewolf/b5627b28-c33f-421e-bf06-095a1f38a347/scratchpad/hidden_column_copy_probe.py`` and is ready to become a regression test.

**This is not a feature; it is a data-integrity bug in shipped behaviour.** It should be fixed
before any of the work below, and it changes the shape of item 1.

---

## 1. Selection statistics

**Report effort 1. Revised: 2.**

### What exists

- `PolarsTableModel.data()` (`models/polars_table_model.py:60`) returns the **typed** value under
  `Qt.ItemDataRole.UserRole`, so statistics can read real numbers rather than parsing display text.
- `selection_for_export()` already maps proxy rows to source rows and skips hidden columns.
- `result_summary_label` (`main_window.py:1375`) is a persistent label on the results page.

### What the work is

1. Aggregate over the selected source rows per column, off `self._source_model.frame()` in one
   pass rather than per `QModelIndex`.
2. Emit a `selection_stats_changed` signal from `selectionModel().selectionChanged`.
3. Render into a new label on the results page.

### Traps

- **Translate visual to logical, and fix the hidden-column defect first.** `selection_for_export()`
  is reusable — `column_order` is exactly the visual→model map, and the TSV serializer already
  uses it that way — but it is reusable only once the mismatch above is corrected. Building
  statistics on the current pairing would inherit the same wrong-column bug.
- **Not the status bar, despite the report's title.** The 0.9.0 notes record moving the result
  summary *out* of the status bar because a ten-second timeout made it vanish. Put this next to
  `result_summary_label` instead. Note that label is not adjacent to the grid: the truncation
  notice, error label, filter/export row and filter-error label all sit between it and the table
  (`main_window.py:1375-1427`), so placement needs a deliberate choice, not "next to the existing
  one".
- Mixed selections need a rule: count and distinct always; sum/avg/min/max only when every
  selected column is numeric.
- Assumption, not verified in this codebase: `selectionChanged` on a large drag-selection fires
  often enough to matter. Aggregating off the frame rather than off `selectedIndexes()` makes the
  question moot, so it costs nothing to build it that way.

---

## 2. "Count all rows"

**Report effort 1. Revised: 4** (3 if scoped to DuckDB only). The report badly underestimated this.

### What exists — more than expected

`QueryResult.total_row_count: int | None` already exists (`domain/models.py:94`) and
`main_window.py:888` already renders it:

```python
if result.total_row_count is not None and result.total_row_count != result.preview_row_count:
    row_text = f"showing {result.preview_row_count} of {result.total_row_count} rows"
```

That branch is unreachable today. The DuckDB adapter passes `total_row_count=None`
(`execution/registry.py:142` and friends); the Spark adapter passes
`legacy_result.row_count` (`registry.py:464,477`), which equals `preview_row_count`, so the `!=`
guard never fires. The display half is built and dead.

The count query itself also has a precedent: the XLSX full-export path already runs
`SELECT count(*) FROM ({request.executable_sql})` with `request.parameters`
(`registry.py:339-341`) to enforce the row cap. The wrapper is proven; parameter binding through
it is proven.

### What the work is

Presentation is free. The cost is where the count runs.

- **Route A — count during execution.** Populate `total_row_count` in `_DuckDBAdapter` whenever the
  preview truncated. No new UI; the dead branch lights up. Cost: a second query on every truncated
  result, including the large-file case the preview limit exists to protect.
- **Route B — count on demand** from a link in the truncation notice, built from
  `_EditorTabState.last_request`. Cost: the isolation problem below.

Route B is the better product answer, with the control disabled while a query is running.

### Traps

- **`QueryController` is single-slot.** `execute()` returns `False` unless status is `IDLE`
  (`query_controller.py:60`), so an on-demand count cannot go through the normal path without
  either failing or blocking the user's next query.
- **A second request would pollute shared state.** Results dispatch by request id through
  `_result_origin_by_request_id` (`main_window.py:297`) into `_render_query_result`, the Messages
  panel and history — a count would overwrite the grid, log a spurious message, and write a query
  the user never typed into `~/.wherewolf/history.json`. Isolation is required; the existing
  independent `ExportController` worker (`desktop/export_controller.py:70`) is the natural model,
  and re-using it is cheaper than inventing a new worker type.
- **Multi-statement requests must be rejected.** `executable_sql` can hold several statements
  joined with `;\n\n` after translation (`services/execution_request_builder.py:52-57`); wrapping
  that in a derived table is invalid. Gate on statement count and on statement kind (DDL/DML have
  no meaningful row count).
- **Spark must be excluded or given its own path.** It already reports preview count as total
  (`registry.py:477`) and has no full-export adapter (`registry.py:508`).
- **Staleness.** `ExecutionRequest` captures `source_snapshots`
  (`execution_request_builder.py:68`), but only full export checks them (`registry.py:603`). A
  count run minutes after the preview can legitimately disagree with the rows on screen; either
  check the snapshots or label the count with its own timestamp.
- `ORDER BY … LIMIT` inside the wrapped query is *not* a problem — the derived-table count counts
  that query's result, which is the intended answer. (The first draft claimed otherwise; wrong.)

---

## 3. Jump to the error position

**Report effort 2. Revised: 3.**

### What exists

- `SqlEditor` defines a red squiggle indicator: `_diagnostic_indicator` and `indicatorDefine(...)`
  with `SquiggleIndicator` (`widgets/sql_editor.py:84,226`).
- `_show_parse_diagnostic(diagnostic)` (`sql_editor.py:435`) fills an indicator range from a
  `SqlDiagnostic`.
- `SqlDiagnostic(message, severity, start_line, start_column, end_line, end_column)`
  (`domain/models.py:157`) is the carrier.

### What the work is

1. Parse position out of the engine's error text (DuckDB embeds `LINE n:` plus a caret line) — a
   pure function in `services/`, no Qt, cheap to test.
2. Build a `SqlDiagnostic` from `QueryResult.error_message` / `error_detail` and hand it to a new
   **public** `SqlEditor.show_execution_error(...)`; `_show_parse_diagnostic` is private and today
   is reachable only from the formatting path.
3. Add the actual "jump": that method marks a range but never moves the caret, so
   `setCursorPosition(...)` and `ensureLineVisible(...)` are new.
4. Widen the highlight: it currently ignores `end_line`/`end_column` entirely and always marks
   exactly one character at `start_column` (`sql_editor.py:443`).
5. Make the Messages panel error line clickable, routing to the same call.

### Traps — this is where the estimate moved

- **Three separate offset problems, not one.** The engine's reported position indexes the SQL it
  actually ran, and three transforms sit between that and the editor's text:
  1. *Statement selection.* Only the selected statement or the statement under the cursor is sent
     (`sql_editor.py:367`), so offsets are relative to that fragment, not the document. The
     fragment's start offset must be added back.
  2. *Whitespace.* `ExecutionRequestBuilder` strips the SQL (`execution_request_builder.py:32`).
  3. *Named parameters.* They are rewritten to `?` before execution (`main_window.py:644`), which
     shifts every position after the first parameter.
  Dialect translation is a fourth and worst case: sqlglot regenerates the text
  (`execution_request_builder.py:50-57`) and no offset map exists. Same-dialect is a necessary but
  **not sufficient** condition for a trustworthy caret — the first draft got this wrong.
- **A stale squiggle will persist.** `_clear_diagnostic_indicator()` has exactly one caller, at the
  start of the format routine (`sql_editor.py:411`); typing does not clear it. An execution-error
  squiggle would therefore sit on the line until the user happens to format. Clearing on
  `textChanged` needs to be added deliberately.
- There is no existing execution-error→editor path to copy. `main_window.py:665` does fabricate a
  `SqlDiagnostic`, but for a pre-execution `TranslationError`, and it reaches only Messages and the
  status bar, never the indicator (`main_window.py:650,1777`).
- Error-text parsing must degrade silently: a DuckDB message-format change should cost the
  highlight, not raise.

**Recommendation:** ship the clickable message and the caret only for the same-dialect,
no-parameter, single-statement case, and show the message without a position otherwise. Marking
the wrong token is worse than marking none.

---

## 4. Cell value inspector

**Report effort 2. Revised: 2 floating, 3 embedded.**

### What exists

- `ValueCountsWindow` (`widgets/value_counts_window.py`) is a working non-modal floating window,
  including the lifetime pattern: retention in `_value_counts_windows`, removal on close
  (`main_window.py:300,1227-1239`), bulk close on shutdown (`main_window.py:1891`).
- `PolarsTableModel` serves the untruncated typed value under `UserRole`, so the inspector can show
  the real object rather than elided cell text.

### What the work is

1. A read-only monospace text area with a copy button.
2. Populate from `selectionModel().currentChanged`, pretty-printing when the value is (or parses
   as) JSON.
3. Open it from the body context menu (`result_table_view.py:257`) and a shortcut.

### Traps

- **Do not render through `format_cell_value()`.** It is TSV escaping
  (`clipboard_serializers.py:19`) — it stringifies Python structures and doubles quotes, so JSON
  parsing downstream of it is unreliable. The inspector should take the raw `UserRole` value.
- **The context menu does not make the clicked cell current** (`result_table_view.py:282`), so an
  "inspect current cell" action can open a previously selected cell. Set the index first.
- **Docked is cheaper than the first draft claimed, embedded is not.** A real `QDockWidget` follows
  the existing dock pattern and persists through `QMainWindow.saveState()/restoreState()`
  (`main_window.py:538,1845`) — no new settings work. It is only an *embedded* pane in the results
  page that would require converting that flat `QVBoxLayout` (`main_window.py:1368-1430`) to a
  splitter, and `restore_splitter_sizes` accepts exactly two sizes
  (`services/settings_service.py:419`), so it cannot be reused unchanged for a second splitter.
  (`ValueCountsWindow` has a splitter but does **not** persist its sizes — the first draft claimed
  it did.)
- Cap very large values with an explicit "showing first N KB" notice rather than loading a
  multi-megabyte string into the widget. Assumed, not measured.

---

## Summary

| # | Feature | Report | Revised | Why it moved |
|---|---------|--------|---------|--------------|
| 1 | Selection statistics | 1 | 2 | Blocked behind the hidden-column defect; label placement is a real choice |
| 2 | Count all rows | 1 | 4 | Single-slot controller, shared result routing, multi-statement and Spark cases |
| 3 | Jump to error position | 2 | 3 | Four separate offset transforms; no existing execution-error→editor path |
| 4 | Cell value inspector | 2 | 2 / 3 | 2 as a window or dock; 3 only if embedded in the results page |

**Suggested order:** the hidden-column defect first, then **4, 1, 3, 2** — ascending by how much
shared state each touches.

The recurring theme survives the fact-check: three of the four are cheap because earlier releases
already built the primitive — typed `UserRole` values, the squiggle indicator, the floating-window
pattern, the `count(*)` wrapper in the exporter, and a `total_row_count` field wired end-to-end but
never populated.

---

## Corrections after fact-check

Claims in the first draft that the code disproved:

1. "`selection_for_export()` needs its own method" — wrong conclusion. `column_order` *is* the
   visual→model map and the serializer already uses it. Reuse is viable; the real problem is that
   the pairing is broken for hidden columns, which neither the draft nor the fact-check caught
   until the probe was run.
2. "`result_summary_label` is directly above the grid" — it is not; four widgets sit between them.
3. "The indicator is cleared as soon as the user types" — false. One caller, in the format routine.
   The correct concern is the opposite: the squiggle goes stale.
4. "`main_window.py:665` establishes the execution-error→diagnostic pattern" — it is a
   pre-execution `TranslationError` that never reaches the editor indicator.
5. "`ORDER BY … LIMIT` inside the subquery changes the answer" — false for a row count, and the
   XLSX exporter already uses the same wrapper.
6. "A docked pane requires a `QSplitter` plus settings persistence" — only an embedded pane does; a
   `QDockWidget` reuses existing state persistence.
7. "Work item 10 already did splitter persistence for the value-counts window" — it added a
   splitter, not persistence.
8. Speculation about author intent behind `total_row_count` has been removed; the source cannot
   establish it.

Unverified assumptions are now labelled as such rather than stated as fact (`selectionChanged`
frequency, large-value UI stalls, how nested polars values surface).
