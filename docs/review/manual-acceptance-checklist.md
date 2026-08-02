# 0.6.0 manual acceptance checklist

This is a maintainer-owned release gate. Complete every applicable item on current supported
Windows, macOS, and a supported Linux desktop. Do not mark an item complete from an offscreen
test or CI result. Record a failure or limitation in the result space rather than changing the
expected result.

## Platform runs

- [ ] Platform: __________  Date: __________  Clean install and native launch
  - Steps: Install the candidate wheel into a new environment with `uv tool install <wheel>`.
    Run `wherewolf` from a terminal, then inspect the desktop and the terminal process list.
  - Expected: One native Wherewolf window appears; no browser tab opens and no local web server
    starts. The terminal command remains the desktop application's process.
  - Result / issue: _________________________________________________________________

- [ ] Platform: __________  Date: __________  Native multi-file dialog
  - Steps: In the launched app, choose **Add Datasets…**. Select two supported files in the
    operating system dialog, then cancel and open it again.
  - Expected: The operating system's multi-file dialog appears where supported; both selected
    files enter the Dataset Catalog; cancel adds nothing.
  - Result / issue: _________________________________________________________________

- [ ] Platform: __________  Date: __________  File-manager drag and drop
  - Steps: Drag a third supported local file from the platform file manager onto the Dataset
    Catalog.
  - Expected: The catalog accepts the drop and shows the new dataset; unsupported files or
    directories are not added.
  - Result / issue: _________________________________________________________________

- [ ] Platform: __________  Date: __________  Catalog aliases and schema
  - Steps: Rename a catalog alias, attempt a case-only duplicate alias, use **Refresh Schema**,
    and use the catalog action to insert the alias into the editor.
  - Expected: A valid alias changes, a case-insensitive duplicate is rejected with an explanation,
    schema columns/types or the real schema error are shown, and insert places the alias at the
    editor cursor.
  - Result / issue: _________________________________________________________________

- [ ] Platform: __________  Date: __________  Completion and format shortcut
  - Steps: Type a `FROM` or `JOIN` clause and invoke completion with **Ctrl+Space** (the platform
    equivalent on macOS). Type deliberately unformatted SQL and invoke **Format SQL** with
    **Ctrl+Shift+F** (the platform equivalent on macOS).
  - Expected: Completion offers catalog aliases/columns when applicable, and formatting changes
    only the SQL presentation without dropping statements or making the UI unresponsive.
  - Result / issue: _________________________________________________________________

- [ ] Platform: __________  Date: __________  Query responsiveness and cancellation
  - Steps: Run a query that takes long enough to interact with the app while it is active. Switch
    docks, select editor text, then choose **Cancel** or press **Ctrl+.**.
  - Expected: The window continues to repaint and accept interaction while the query runs;
    cancellation first reports that it was requested and eventually reports completion or a clear
    terminal result.
  - Result / issue: _________________________________________________________________

- [ ] Platform: __________  Date: __________  Clipboard integration
  - Steps: Run a query with multiple rows and columns. Select a rectangular range, use the normal
    copy shortcut, then use **Copy with Column Names**. Paste each result into the platform's
    spreadsheet application.
  - Expected: Values paste as tab-separated cells in visual row/column order; the second paste
    includes the headers.
  - Result / issue: _________________________________________________________________

- [ ] Platform: __________  Date: __________  Preview sorting versus query ordering
  - Steps: Click a result header to sort ascending, descending, then clear the sort. With a sort
    active, inspect the disclosure. Then choose **Apply Ascending Order to Query** from that
    header's context menu and run the edited query.
  - Expected: Header clicks affect only the preview and show **Sorted preview only.**; clearing
    restores query order. Applying order changes the SQL/query result only after it is run.
  - Result / issue: _________________________________________________________________

- [ ] Platform: __________  Date: __________  Result-grid column operations
  - Steps: Move a column, resize it by dragging, auto-size it from the header menu, hide it, show
    all columns, and reset columns to default.
  - Expected: Each operation affects the visible grid as named; reset restores visible columns and
    their default order.
  - Result / issue: _________________________________________________________________

- [ ] Platform: __________  Date: __________  Preview and full DuckDB export
  - Steps: Run a query with more than the preview limit where practical. Use **Export Preview…**
    to write a CSV, then use **Export Full Results…** to a different CSV path and inspect both
    files.
  - Expected: Preview export contains only the displayed bounded rows. Full export re-executes the
    query and contains all rows; the application remains responsive and reports success or a
    concrete error. Do not infer full-export success from the preview file.
  - Result / issue: _________________________________________________________________

- [ ] Platform: __________  Date: __________  Restart, geometry, layout, and history
  - Steps: Move/resize the window, rearrange docks and splitter, run a query, close the window,
    then launch it again. Select the newly saved History entry.
  - Expected: Real-window geometry, dock arrangement, and splitter sizes are restored; the
    history entry restores SQL and available datasets without automatically running it.
  - Result / issue: _________________________________________________________________

- [ ] Platform: __________  Date: __________  About and legal notice accuracy
  - Steps: Open **Help → About**. Compare the displayed GPL-3.0-only text and the reference to
    `LICENSES/MIT-pre-0.6.txt` with `LICENSE`, `LICENSES/MIT-pre-0.6.txt`, and `NOTICE.md` in the
    candidate source/artifacts.
  - Expected: The dialog and files accurately state GPL-3.0-only for 0.6.0 while preserving the
    MIT terms and grants for releases through 0.5.2.
  - Result / issue: _________________________________________________________________

- [ ] Platform: __________  Date: __________  Optional Spark workflow
  - Steps: On a platform with Java and `wherewolf[spark]` installed, launch the app, select Spark,
    run a small supported-file query, then select **Export Full Results…**.
  - Expected: Spark is available only with the extra and Java, and the query can run. Full export
    reports that it is currently available only for DuckDB; it must not silently materialize or
    claim a Spark full-export result.
  - Result / issue: _________________________________________________________________

## Final release artifacts

- [ ] Platform: __________  Date: __________  Wheel license contents
  - Steps: Build the release wheel, list it with `unzip -l <wheel>`, and inspect its `.dist-info`
    metadata.
  - Expected: The wheel contains `LICENSE` and `LICENSES/MIT-pre-0.6.txt`; metadata declares
    `GPL-3.0-only`; the `wherewolf` and `wherewolf-desktop` console scripts are present.
  - Result / issue: _________________________________________________________________

- [ ] Platform: __________  Date: __________  Source-distribution license contents
  - Steps: Build the source distribution and list it with `tar -tzf <sdist>`.
  - Expected: The source distribution contains `LICENSE` and `LICENSES/MIT-pre-0.6.txt` alongside
    the package source.
  - Result / issue: _________________________________________________________________
