# UI follow-ups implementation

- Date: 2026-08-02
- Objective: Implement the `ui-followups` plan on `feat/ui-followups`.
- Files modified: main window, history dock, completion adapter/editor, targeted tests, and manual acceptance checklist.
- Tests added: toolbar visibility across 1024/1280/1440/1600px; interactive history sizing; second-precision timestamp tooltip; query-only history restore; visible QScintilla completion popup; results-area query errors.
- Design decisions: Query controls use a dedicated second toolbar row to preserve their full captions. Completion uses Scintilla's autocomplete popup API instead of its inactive user-list API. History selection deliberately no longer mutates the catalog.
- Results: Targeted and full test suites, Ruff, and ty pass. Manual acceptance remains for toolbar/completion visual composition on supported desktops.
