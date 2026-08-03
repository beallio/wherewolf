# Changelog

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
