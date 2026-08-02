# Changelog

## [0.6.0] - Unreleased

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

### Removed

- The Streamlit runtime and browser-based UI.

### Release candidate gate

- This section is not a release sign-off. The maintainer must complete
  `docs/review/manual-acceptance-checklist.md`, including real desktop, cross-platform, legal,
  and final-artifact checks, before tagging 0.6.0.
