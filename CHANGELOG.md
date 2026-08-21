# Changelog

## Unreleased

### Fixed

- **JSON Lines files are read as JSON Lines.** `.jsonl` was accepted by the catalog, offered in
  the file dialog, and advertised in the README, but the DuckDB engine had no branch for it and
  fell through a catch-all that parsed the file as CSV — so a JSON Lines dataset loaded as one
  garbage column with no error. Format dispatch now goes through `SourceFormat` with no fallback,
  and a suffix the engine cannot read is reported instead of guessed at.

## [0.10.0] - 2026-08-20 — Wherewolf has a face

### Added

- Wherewolf now has an application icon instead of Qt's default placeholder, and
  `wherewolf install-desktop-entry` installs the desktop entry and themed icons that a
  Wayland desktop needs to display it. `wherewolf remove-desktop-entry` undoes it.

## [0.9.3] - 2026-08-20 — The fields panel copies the cell you selected

### Fixed

- Copying from the dataset fields panel now copies just the selected cells instead of the
  whole row.

## [0.9.2] - 2026-08-19 — Editor shortcuts do what the menu says

### Fixed

- `Ctrl+T` opens a new query tab while the SQL editor has focus instead of swapping the
  current line with the one above it, and `Ctrl+/` toggles comments through the normal
  shortcut path rather than a key-press interception.

## [0.9.1] - 2026-08-18 — Queries stay with their tabs, exports keep parameters, and catalog saves recover

### Fixed

- Parameterized DuckDB exports now use the same bound request as preview, while history keeps the
  reusable named-parameter SQL and never stores entered values.
- `{dataset}` is replaced only in SQL code, not in strings, quoted identifiers, or comments.
- Edit commands, Find/Replace, and theme previews follow every open editor tab rather than the
  tab that happened to exist when the window opened.
- Opening a SQL file preserves a non-pristine buffer in its own tab, and restored file drafts
  correctly show as modified when they differ from disk or the file cannot be read.
- Result ordering now refuses a direct saved-query result instead of editing unrelated SQL;
  successful queries still reach history after their origin tab closes.
- Returned catalog files recover from their unavailable state, catalog-save failures stay visible
  and retry safely, and saved-query filtering no longer rereads the store for each keystroke.

## [0.9.0] - 2026-08-17 — Your work survives a restart, filenames are readable, and queries get tabs

### Added

- **The dataset catalog is restored when you reopen Wherewolf.** Datasets used to vanish on
  exit, so every session began by re-adding the same files and waiting through schema
  inspection again. The catalog now persists to `~/.wherewolf/catalog.json` and comes back on
  launch, with schemas re-inspected in the background. A file that has moved or been deleted is
  kept and marked "Unavailable — file not found" rather than disappearing without explanation,
  because a query in your history that references it should still make sense.
- **The query you were writing is still there next time.** Only *executed* queries reached
  history, so an unfinished draft — the interesting one, because it was the one that wasn't
  working yet — was lost on close. The editor buffer now survives a restart. `.sql` files can
  also be opened and saved outright, with the filename in the window title and a marker when
  there are unsaved changes.
- **Multiple query tabs.** `Ctrl+T` opens one, `Ctrl+W` closes it, and each tab keeps its own
  buffer, its own file, and its own results. Switching tabs shows that tab's last result, and a
  query still running when you switch will not write its result into whichever tab you happen
  to be looking at. Open tabs are restored on launch.
- **A saved-query library.** Name a query, give it `:parameters`, and run it again later with
  new values — useful for the same data-quality rule against each week's export. A `{dataset}`
  placeholder binds to a catalog alias chosen at run time. Parameter values are bound rather
  than pasted into the SQL, so a value containing quotes or a semicolon is data and cannot
  change what the statement does. Parameterised queries are DuckDB-only; Spark reports that it
  cannot run them rather than guessing.
- **History can be searched and pinned.** A filter box narrows the list by substring, and
  pinned records sort to the top and are exempt from the hundred-entry cap — pinning something
  and then running a hundred more queries no longer quietly loses it.
- **Value counts can be exported** in CSV, Excel, or Parquet, and the table sorts by count and
  percentage numerically, so ascending order finds the rarest values instead of putting 100
  before 9.
- **The schema panel filters columns by name**, which matters on a two-hundred-column Parquet
  file where finding one column otherwise means scrolling.

### Changed

- **The catalog shows filenames.** The File column previously rendered the whole absolute path,
  so at any realistic dock width it displayed the directory prefix every row shares and cut off
  the filename that distinguishes them. File now shows the filename, a new Folder column shows
  the parent directory dimmed and elided from the left, and both carry the full path on hover.
  The File column is also draggable again — it had been set to stretch, which silently made it
  impossible to resize.
- **The schema panel names its dataset by filename**, with the full path on hover, and moves
  profiling warnings to their own line so a long warning no longer pushes the dataset name
  around.
- **Query results keep their summary on screen.** Engine, row count, elapsed time and the
  truncation warning used to appear in the status bar for ten seconds and then vanish, so
  "was this truncated?" meant running the query again.
- **The value-counts window has an adjustable splitter** between the table and the chart.

### Fixed

- **The value-counts chart can be scrolled to the last row.** With the default Top N of 50 the
  chart drew roughly 1100px of bars into a pane a few hundred pixels tall and simply painted
  the rest off the widget, where no scrolling, resizing, or dragging could reach it. You saw
  the top eight bars with no indication the other forty-two existed.
- **Changing Top N runs one query instead of one per keystroke.** Clicking the arrow from 50 to
  60 started ten concurrent scans of the column, and a slow early result could land after a
  fast later one and overwrite it.
- **The schema panel's tooltip no longer names the wrong file** when the selected dataset fails
  to load.

## [0.8.0] - 2026-08-11 — History actions, self-sizing columns, cell selection, and a working Ctrl+/

### Added

- **Query history now has a right-click menu.** Select one row or many with `Shift` and
  `Ctrl`, then delete the selection or save it straight to a `.sql` file. Deleting asks first
  and names how many records will go, because history deletion is permanent. Saving writes a
  single file, newest query first, each one preceded by a `-- <timestamp>` comment so the
  file reads as a work log rather than a pile of statements.
- **Result columns size themselves to their contents**, capped so that one long text column
  cannot push everything else off-screen. Both the behaviour and the cap live in Preferences —
  the cap defaults to 300px and accepts any width between 50 and 2000. The sizing samples a
  bounded number of rows, so it costs the same few milliseconds whether the preview holds a
  thousand rows or a hundred thousand.
- **Individual cells can be selected** in the dataset catalog and the schema panel, instead of
  always taking the whole row. Click the row number on the left to select the entire row as
  before. In the schema panel, selecting any cell in a row still identifies that row's column,
  so inserting column names into the editor works from whichever cell you happened to click.

### Changed

- **Execution errors now come to you.** A failed query raises the Messages tab and prints the
  error in red — a red that was chosen separately for the light and dark themes so it stays
  readable in both. Successful queries leave your current tab alone, and diagnostics that
  appear while you type never steal focus.

### Fixed

- **`Ctrl+/` toggles comments.** The shortcut had never worked: the editor is a QScintilla
  widget, which claims `Ctrl`-modified keys before Qt's shortcut system ever sees them, so the
  binding was dead on arrival while the Edit-menu entry kept working. Commenting a block also
  keeps your selection now, so pressing it twice returns the text exactly as it was rather than
  commenting a line you never selected.
- **Undo survives loading a query from history.** Double-clicking a history entry replaced the
  editor's contents and discarded the undo history with it, so whatever you had been writing
  was unrecoverable. One `Ctrl+Z` now brings it back. The same fix applies to "Apply Order to
  Query" from a results header, to comment toggling, and to Replace All — each had silently
  emptied the undo buffer, taking every earlier edit along with the change it made.

## [0.7.1] - 2026-08-06

### Fixed

- Column profiling now reports when it fails. Previously a failed profile left the statistics
  columns blank, cleared the "profiling skipped" notice, and showed no error at all — which
  looked identical to nothing having happened. The failure is now named in the schema panel,
  and the column list stays visible because the schema itself is still valid.
- The "profiling skipped" notice stays until profiling actually succeeds, instead of being
  cleared by a failed attempt.

### Added

- A "Profiling…" indicator while profiling runs, with the Profile button disabled so the same
  dataset cannot be queued twice.

## [0.7.0] - 2026-08-04

### Added

- An application-wide colour theme with **Light**, **Dark** and **Follow system** modes,
  selectable in Preferences and applied at startup. Previously only the SQL editor was themed.
- **Value counts** for any column: right-click a row in the schema panel to open a floating
  window showing a value/count/percentage table alongside a bar chart, with a configurable
  Top N and the total distinct count. Values can be selected and copied. The chart is drawn
  with `QPainter`, so no plotting dependency is added.
- Schema panel rows can now be selected and copied with `Ctrl+C` or the right-click menu.
- Two further SQL editor themes, Monokai and Nord, bringing the total to seven.

### Changed

- Editor themes now preview live as you move through the Preferences drop-down, and revert
  if you cancel, instead of only applying after OK.
- Both toolbars share a single row by default while remaining independently movable. Saved
  layouts from earlier versions are reset once so the change takes effect.
- The execution-engine drop-down no longer widens to fit an unavailability message. An
  unavailable engine stays greyed out and explains itself in a tooltip, which takes the
  control from 414px to 75px.

### Fixed

- History columns can be reordered. The first column needed `setFirstSectionMovable`, which
  `setSectionsMovable` alone does not imply, so the Timestamp column was frozen in 0.6.1.
- The SQL editor's horizontal scrollbar disappears again when long text is removed. Scroll
  width only ever grew, so it stayed visible over short text.

## [0.6.1] - 2026-08-04

### Added

- File menu now exposes `Add Datasets…` and a `Quit` action bound to `Ctrl+Q`.
- Keyboard mnemonics on every top-level menu (`Alt+F`, `Alt+E`, `Alt+Q`, `Alt+V`, `Alt+H`).
- An elapsed-time counter in the status bar while a query runs, continuing through cancellation.
- A banner distinguishing a successful zero-row result from no result at all.
- Datasets skipped as duplicates are now reported rather than silently ignored.
- Alternating row colours in the results grid.
- Column reordering in the dataset catalog, schema and history views, matching the results grid.
- Three further SQL editor themes: Solarized Dark, Solarized Light and High Contrast.
- A `Help` → `SQL Dialect Reference` submenu linking to the DuckDB, PostgreSQL, Oracle, MySQL,
  Microsoft T-SQL, SQLite and Spark SQL documentation.

### Changed

- Export format and scope moved out of the results toolbar into a modal dialog opened from the
  `Export` button, which remembers the last format and scope used. The `Export Preview…`,
  `Export Full Results…` and `Export Selection…` menu actions still export directly.
- Dropping files onto the window now takes the same path as `Add Datasets…`, so dropped files
  get schema inspection and status feedback instead of being added silently.
- The preview-row limit input is constrained to the width of its longest valid value.

### Fixed

- Quitting no longer blocks indefinitely when background workers are running: cancellation is
  requested before waiting, and every wait is bounded.
- Cancelling a query no longer has its status message immediately overwritten by the elapsed-time
  counter.
- The SQL editor's horizontal scrollbar now tracks actual content width, so it no longer appears
  for text that fits.

## [0.6.0] - 2026-08-02

### Changed

- Wherewolf is a native PyQt6 desktop application. The `wherewolf` command no longer opens a
  browser interface or starts a local web server.
- The default execution engine is DuckDB; PySpark is available only through the `spark` optional
  dependency extra and a compatible Java runtime.
- Package metadata and new release artifacts are GPL-3.0-only. MIT grants for releases through
  0.5.2 remain valid.

### Added

- Dataset catalog, schema, history, messages, and translation desktop panels.
- QScintilla SQL editing, completion, formatting, asynchronous execution, cancellation, and a
  typed result grid with clipboard and local-preview ordering controls.
- Preview export and direct-to-disk DuckDB full export, migration of version-1 history records,
  clean installed-wheel smoke coverage, and a cross-platform Qt smoke matrix.
- Oracle and PostgreSQL as SQL **source dialects**, transpiled to the local DuckDB or Spark
  engine. Execution backends remain DuckDB and Spark only. Oracle `ROWNUM` and `FROM DUAL`
  are reported before execution rather than failing at the engine.
- Column profiling in the schema panel: null percentage, approximate distinct count, min,
  max and mean, computed with DuckDB `SUMMARIZE` on a background thread. Profiling on
  dataset load is on by default and skipped for sources above a configurable size.
- `wherewolf --version`, reporting the release version and the build commit, answered
  without loading Qt so it works headless.
- SQL expressions in the preview filter (`age > 40`, `name = 'bob'`), with plain text still
  matching as a substring and invalid expressions reported without clearing the grid.
- Data-type badges in result headers (`age [INT]`, `when [DATE]`), a per-dataset schema
  selector, dock restore from the View menu, sortable history with separate timestamp and
  query columns, Find/Replace, Select All, and a validated preview row-count input
  accepting 10 to 100000.

### Fixed

- A SIGSEGV when running a second query. DuckDB loads pyarrow lazily during
  `relation.pl()`, and pyarrow's bundled mimalloc initialised its thread-local heap on a
  worker thread; once that thread exited, every later thread faulted in `mi_thread_init`.
  pyarrow is now imported on the main thread at startup.
- Full exports reported plain success even when a source file had changed underneath them.
  Source warnings are now shown.
- The export dialog suppressed the overwrite prompt, silently replacing existing files.
- The export save dialog offered every format regardless of the one selected.
- Editor text was unreadable: unstyled tokens rendered light-on-light, and line numbers were
  clipped by a margin sized from space characters rather than digits.
- The Preferences font size never resized the editor, because the lexer's per-style fonts
  were left untouched.
- Ctrl+C and the Edit menu's clipboard commands always acted on the SQL editor rather than
  the focused widget.
- Selecting a history entry also rewrote the dataset catalog and re-ran schema inspection.
- The wheel smoke test leaked a virtual environment per run.

### Removed

- The Streamlit runtime and browser-based UI.
- A "Check for updates on startup" preference that had no implementation behind it.

### Verification status

- Automated coverage: 433 tests across Python 3.12 and 3.14, plus an offscreen Qt smoke
  matrix on Linux, macOS and Windows, a clean-environment wheel install, and a Spark tier.
- `docs/review/manual-acceptance-checklist.md` is **not signed off**. Native dialog
  appearance, real clipboard and drag-and-drop behaviour, and responsiveness under a long
  query remain unverified on every platform. No performance measurements were taken. Spark
  is exercised only on Linux with one JDK, `local[1]`, and small data.
