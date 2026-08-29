# Plan: directory-backed saved-query library (sql-directory-library)

## Problem Definition

The Saved Queries dock is backed by a single JSON document at
`~/.wherewolf/saved_queries.json`. The records are invisible to every other tool: they
cannot be edited in an editor, searched with `grep`, tracked in Git, or synchronised as
files. The window also has no way to overwrite a saved query's SQL, because
`_open_saved_query_in_new_tab` produces an untitled tab that `Ctrl+S` cannot write back.

Replace the JSON document with a **directory of `.sql` files** chosen in Preferences. The
dock lists every `.sql` file found under that directory, recursively. A saved query
becomes an ordinary file, so opening one gives a file-backed tab and `Ctrl+S` overwrites
it.

Confirmed product decisions:

1. `description` is the leading comment block at the top of the query, parsed from the
   file. It is never written separately.
2. No migration. Existing `saved_queries.json` records are not converted or read.
3. The scan is recursive; a relative path becomes the displayed query name.
4. The `.sql` suffix matches case-insensitively.
5. Refresh is explicit (a Refresh command in the dock). No `QFileSystemWatcher`.

## Architecture Overview

```
PreferencesDialog ──saves──> SettingsService (v1/saved_queries/directory)
        │                              │
        └──browse──> FileDialogService.choose_directory
                                       │
MainWindow ──constructs/repoints──> SavedQueryDirectory(directory)
        │                              │ get_all() reads *.sql recursively
        └──builds──> SavedQueriesDock ─┘
```

Layering is unchanged: `SavedQueryDirectory` is GUI-free storage, `SavedQueriesDock`
stays a passive widget that emits the selected record, and `MainWindow` performs every
mutation and every user-visible message. Execution, `{dataset}` binding, `:parameter`
binding, history, and result provenance are untouched, because they operate on SQL text
and never on the record.

## Core Data Structures

```python
@dataclass(frozen=True, slots=True)
class SavedQuery:
    id: str           # absolute file path, stable for the lifetime of the file
    name: str         # POSIX-relative path without the suffix, e.g. "reports/weekly"
    description: str  # leading -- run or leading /* */ block, markers stripped
    sql: str          # full file text
    updated_at: str   # ISO-8601 UTC, derived from st_mtime
```

`created_at` is dropped: the filesystem does not record a portable creation time
(`st_ctime` is inode-change time on Linux).

## Public Interfaces

```python
class SavedQueryDirectory:
    def __init__(self, directory: Path) -> None: ...
    @property
    def directory(self) -> Path: ...
    def set_directory(self, directory: Path) -> None: ...
    def get_all(self) -> tuple[SavedQuery, ...]: ...
    def save_query(self, *, name: str, sql: str) -> SavedQuery: ...
    def rename_query(self, query_id: str, name: str) -> SavedQuery | None: ...
    def delete_query(self, query_id: str) -> bool: ...

def extract_description(sql: str) -> str: ...
```

`SettingsService`:

```python
DEFAULT_SAVED_QUERY_DIRECTORY = Path.home() / ".wherewolf" / "queries"
def _saved_query_directory_key(schema_version: str) -> str  # v1/saved_queries/directory
@property saved_query_directory_key -> str
def restore_saved_query_directory(self) -> Path
def save_saved_query_directory(self, directory: Path) -> None
```

`FileDialogService` protocol, `QtFileDialogService`, and `FakeFileDialogService` all gain:

```python
def choose_directory(self, default_directory: Path | None, parent: QWidget | None = None) -> Path | None
```

`SavedQueriesDock` gains `refresh_requested = pyqtSignal()` and a Refresh context action.
Its four existing signals and its filter behaviour do not change.

### Name rules

A name is a relative POSIX path without the suffix. `reports/weekly` saves
`<root>/reports/weekly.sql` and creates `reports/` on demand. Rejected with `ValueError`:
blank names, `\`, NUL, absolute paths, empty path components, `.` and `..` components,
components with trailing dots or spaces (unopenable on Windows), and any name that
resolves outside the configured root. Collisions are rejected by an explicit
`Path.exists()` check rather than silently overwriting.

Case-insensitive uniqueness is deliberately dropped: the filesystem now decides. On this
workstation `Daily.sql` and `daily.sql` can coexist; on APFS or NTFS they collide and the
collision check reports it.

### Scan rules

`get_all()` walks the root recursively, keeps regular files whose suffix casefolds to
`.sql`, skips any path with a dot-prefixed component (`.git`, `.trash`), skips files that
fail to read or decode as UTF-8, and sorts by casefolded relative POSIX path. A missing or
unreadable root yields an empty tuple, and `MainWindow` reports that separately.

## Dependency Requirements

None. `write_atomically` already exists in `src/wherewolf/services/export_destination.py`
and is reused for saved-query writes.

## Testing Strategy

Red-Green-Refactor, in this commit order:

1. `SavedQueryDirectory` and `extract_description` — recursive scan and sort, name
   derivation, case-insensitive suffix, non-`.sql` and dot-directory exclusion,
   unreadable/undecodable skip, `-- run` and `/* */` description parsing, name
   validation and traversal rejection, collision on save and rename, subfolder creation,
   delete, missing root, atomic write.
2. `SettingsService` directory preference — default, round trip, invalid value fallback.
3. `choose_directory` on the protocol, Qt service, and fake.
4. `SavedQueriesDock` — ports the two existing tests to a directory store, plus the
   Refresh action emitting `refresh_requested`.
5. `MainWindow` — ports the eight existing saved-query tests, plus: Open in New Tab
   produces a file-backed tab that `Ctrl+S` overwrites, Delete asks for confirmation and
   honours No, an invalid name reports a status message, and changing the Preferences
   directory repoints the library and refreshes the dock.

Existing pins that must keep passing unchanged: `{dataset}` alias quoting,
`:parameter` prompting and binding, named SQL in history, direct-result ownership across
tab switches, and the saved-query ordering guard.

Removed pins, with justification: the JSON version wrapper, corrupt-JSON handling,
`os.replace` interruption of the whole library, UUID v4 identifiers, and the
`~/.wherewolf/saved_queries.json` default path. All five describe a storage format that
no longer exists.

`tests/conftest.py` isolation moves from `SavedQueryStore.DEFAULT_PATH` to
`SettingsService.DEFAULT_SAVED_QUERY_DIRECTORY`, so a test that does not inject a library
cannot write into a real profile.

## Validation

`./run.sh uv run ruff check . --fix`, `./run.sh uv run ruff format .`,
`./run.sh uv run ty check src/`, `./run.sh uv run pytest`. Manual smoke test: launch the
app, point Preferences at a folder containing nested `.sql` files, confirm the dock lists
them by relative name, run one with `{dataset}` and `:parameter`, open one and overwrite
it with `Ctrl+S`, rename it into a subfolder, and delete it.
