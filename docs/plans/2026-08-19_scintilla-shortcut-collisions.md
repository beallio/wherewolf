# Scintilla shortcut collisions in `SqlEditor`

## Problem Definition

`Ctrl+T` ("New Tab") does nothing while focus is inside a SQL editor; instead the
current line is transposed with the line above it.  `SqlEditor` derives from
`QsciScintilla`, whose built-in command set binds `Ctrl+T` to
`Transpose current and previous lines`.  QScintilla accepts the `ShortcutOverride`
event for every key in that command set, which cancels Qt's shortcut dispatch, so the
`new_tab` `QAction` never receives a `Shortcut` event.  Measured behaviour:

- focus in `SqlEditor`: `ShortcutOverride` accepted by the editor, plain `KeyPress`
  delivered, tab count unchanged, document text transposed.
- focus elsewhere in the same window: override declined, `QAction` `Shortcut`
  delivered, tab count increments.

`Ctrl+/` ("Toggle Comment") collides the same way with Scintilla's
`Move left one word part`.  That collision is currently worked around by intercepting
the key sequence in `SqlEditor.keyPressEvent` and triggering the action directly - a
hack that bypasses Qt's shortcut machinery rather than fixing the collision.

The remaining collisions (`Ctrl+A`, `Ctrl+C`, `Ctrl+V`, `Ctrl+X`, `Ctrl+Y`, `Ctrl+Z`)
map to Scintilla commands with equivalent semantics and are left alone.

## Architecture Overview

Remove the conflicting bindings from the editor's own `QsciCommandSet` during editor
setup, so Qt's normal shortcut dispatch reaches the application actions.  With
`Ctrl+/` unbound from Scintilla the `keyPressEvent` interception is redundant and is
deleted, leaving `SqlEditor._toggle_comment_action` (context `WidgetShortcut`) as the
single handler for that sequence.

## Core Data Structures

- `QsciCommandSet` (`QsciScintilla.standardCommands()`) - the editor-local key map.
- `QsciCommand.setKey(0)` / `setAlternateKey(0)` - clears a binding.
- `_CONFLICTING_SCINTILLA_KEYS: tuple[int, ...]` - module-level tuple of the key codes
  to unbind (`Ctrl+T`, `Ctrl+/`).

## Public Interfaces

No public API changes.  `SqlEditor.keyPressEvent` reverts to the inherited
implementation; `SqlEditor.toggle_comment` and `_toggle_comment_action` are unchanged.

## Dependency Requirements

None.  Uses `PyQt6.Qsci` APIs already in `pyproject.toml` / `uv.lock`.

## Testing Strategy

Red tests first, driving real key events through a shown `MainWindow`:

1. `Ctrl+T` with focus in the editor opens a second tab and leaves the document text
   untouched (no transposition).
2. `Ctrl+/` with focus in the editor toggles the comment on the current line, proving
   the behaviour survives removal of the `keyPressEvent` hack.
3. Unit test on `SqlEditor` asserting `standardCommands().boundTo()` returns no command
   for the conflicting sequences.
