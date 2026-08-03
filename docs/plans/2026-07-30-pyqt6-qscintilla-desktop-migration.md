# Wherewolf Desktop Migration Plan: PyQt6 + QScintilla

**Date:** 2026-07-30  
**Status:** Implementation handoff  
**Repository:** `beallio/wherewolf`  
**Baseline:** Current `main`, package version `0.5.2` at the time of planning  
**Target release:** `1.0.0`  
**Target license:** `GPL-3.0-only`, subject to the licensing gate in Phase 0  
**Target branch:** `feat/pyqt6-desktop`  
**Repository destination for this plan:** `docs/plans/2026-07-30-pyqt6-qscintilla-desktop-migration.md`

---

## 1. Executive decision

Replace the Streamlit presentation layer with a native desktop application built on **PyQt6 and QScintilla**. Preserve and refactor the existing DuckDB, Spark, SQLGlot, Polars, history, and export capabilities behind UI-neutral services.

This is a **desktop-shell rewrite**, not a ground-up rewrite of the query product.

The implementation must make these choices explicit:

1. Wherewolf is a local, trusted, single-user, single-instance application.
2. The default application is a native Qt Widgets application. It does not start a browser, HTTP server, WebSocket session, or embedded web editor.
3. PyQt6 and QScintilla are the selected GUI/editor stack.
4. The project is relicensed to `GPL-3.0-only` before GPL-only dependencies are merged into the distributable application.
5. DuckDB is the default engine and startup path.
6. Spark remains supported, but becomes an optional, lazily imported extra.
7. Only one query may execute at a time.
8. The custom Streamlit filesystem browser is deleted and replaced by native open/save dialogs plus operating-system drag and drop.
9. Streamlit feature parity is a cutover gate. In particular, the replacement must include:
   - selectable result cells, ranges, rows, and columns;
   - type-aware preview sorting;
   - movable and resizable columns;
   - clipboard copying, including column names;
   - a capable SQL editor with syntax highlighting and live completion;
   - catalog- and schema-aware IntelliSense;
   - a Format SQL toolbar action, menu action, and keyboard shortcut;
   - query history, translated SQL, schema inspection, metrics, cancellation, and export.
10. The Streamlit UI remains available only during migration. It is removed before the target release; the project must not maintain two UIs long term.

---

## 2. Problem definition

The current application is functional, but its interaction model is constrained by Streamlit:

- application state is coordinated through `st.session_state`, reruns, cached resources, and widget keys;
- the SQL editor is an Ace web component embedded through `streamlit-ace`;
- the file picker is a custom, in-page filesystem browser rather than the operating system's native dialog;
- result-table behavior is delegated to Streamlit's browser dataframe component;
- desktop conventions such as dock panels, splitters, persistent window state, direct drag and drop, native menus, and native shortcuts require framework workarounds;
- Streamlit-specific CSS targets framework-generated DOM and therefore adds maintenance cost without resolving the underlying desktop mismatch;
- the Streamlit server, browser shell, and rerun model add perceived and actual weight to a single-user local utility.

The desired product is a stateful desktop SQL workbench. The replacement must improve desktop ergonomics without regressing the useful functionality users currently receive from `st.dataframe` and Ace.

### 2.1 Primary outcome

A user launches `wherewolf` and receives a native application window with:

- native multi-file selection;
- a dataset catalog;
- a QScintilla SQL editor;
- schema-aware completion;
- SQL formatting;
- DuckDB and optional Spark execution;
- a spreadsheet-like, read-only result grid;
- query history, schema, translation, messages, metrics, and export;
- persistent desktop layout and preferences.

### 2.2 Success condition

The migration is successful only when the Streamlit runtime and tests can be deleted while all mandatory acceptance criteria in Section 21 remain green.

---

## 3. Scope

### 3.1 In scope

- Relicensing future releases to `GPL-3.0-only`, after confirming the maintainer has the legal authority to do so.
- Replacing Streamlit and `streamlit-ace` with PyQt6 and `PyQt6-QScintilla`.
- A `QMainWindow` desktop shell with menu bar, toolbar, dock widgets, splitters, tabs, and status bar.
- Native multi-file open and save dialogs.
- File drag and drop from Finder, Explorer, and Linux file managers.
- Dataset catalog add, remove, rename, schema refresh, path copy, and insert-alias actions.
- QScintilla SQL editor with syntax styling, line numbers, brace matching, find/replace, selected-statement execution, completion, call tips, formatting, and parse diagnostics.
- A `QTableView` result grid backed by a custom `QAbstractTableModel`.
- Cell/range/row/column selection and clipboard serialization.
- Preview sorting and filtering without mutating the underlying query.
- Explicit handling of the difference between preview sorting and full-query ordering.
- DuckDB execution using a per-execution connection.
- Spark execution through a lazy session manager and request-specific job group.
- One-active-query state machine and request-specific cancellation.
- Immutable execution snapshots for history and export correctness.
- Schema, translation, messages, metrics, history, and settings UI.
- Path-based export rather than session-state byte blobs.
- Backward-compatible migration of existing `~/.wherewolf/history.json` data.
- Cross-platform automated tests and a manual release acceptance matrix.
- Removal of Streamlit code, dependencies, configuration, and tests.
- Updated README, licensing notices, contributor documentation, CI, and release workflow.

### 3.2 Out of scope

- Multi-user or remote-server deployment.
- Authentication, authorization, or tenant isolation.
- Concurrent query execution.
- Remote database connection management.
- A language-server-protocol implementation.
- A general plugin system.
- Notebook semantics or a multi-cell execution model.
- Editing source data through the result table.
- Full-result interactive virtualization for millions of displayed rows. Results remain preview-oriented.
- Native installers in the initial cutover. PyPI/`uv tool` distribution is the initial release path; installers may follow after the Python package is stable.
- Maintaining Streamlit as an alternate supported frontend after `1.0.0`.

---

## 4. Current-state baseline

The agent must inspect the current repository before changing it, but the migration is expected to touch these existing areas:

| Existing path | Current role | Migration disposition |
|---|---|---|
| `src/wherewolf/app.py` | Monolithic Streamlit application, CSS, session state, editor, run/cancel orchestration | Delete at cutover after behavior is represented in desktop modules |
| `src/wherewolf/cli.py` | Launches Streamlit | Rewrite to launch `QApplication` |
| `src/wherewolf/engines.py` | Streamlit-cached DuckDB/Spark singleton factories | Replace with a UI-neutral engine registry/factory |
| `src/wherewolf/ui/file_browser.py` | Custom in-page filesystem explorer | Delete; replace with native dialog adapter and drag/drop |
| `src/wherewolf/ui/results.py` | Streamlit result rendering and in-memory export interaction | Delete; replace with Qt result models/widgets and path-based export |
| `src/wherewolf/execution/duckdb_engine.py` | DuckDB registration and query execution | Retain concept; refactor connection and export lifecycle |
| `src/wherewolf/execution/spark_engine.py` | Lazy Spark session and Spark execution | Retain as optional engine; refactor job cancellation and export |
| `src/wherewolf/execution/models.py` | `QueryResult` | Extend and split into stronger immutable request/result types |
| `src/wherewolf/translation/translator.py` | SQLGlot translation | Retain; tighten statement handling and expose UI-neutral service |
| `src/wherewolf/export/exporter.py` | DataFrame-to-bytes exporter | Replace with file-oriented export service; retain bounded preview export helpers where useful |
| `src/wherewolf/storage/history.py` | JSON history persistence | Retain and migrate to ID-based v2 records |
| `src/wherewolf/constants.py` | engines, dialects, supported extensions | Replace ad hoc constants with enums/capabilities; remove unsupported `.xls` claim |
| `.streamlit/` | Streamlit configuration | Delete at cutover |
| `tests/test_app_flow.py` and other Streamlit tests | Browser-style Streamlit tests | Replace with `pytest-qt` widget and integration tests |
| `pyproject.toml` / `uv.lock` | MIT metadata and Streamlit/Spark mandatory dependencies | Relicense; add Qt/QScintilla; make Spark optional; remove Streamlit |
| `.github/workflows/ci.yml` | Ubuntu-only test matrix | Add headless Qt tests and cross-platform smoke jobs |

The existing core modules are not assumed correct merely because they are retained. The migration must fix lifecycle and correctness defects that directly affect the desktop architecture, especially execution snapshots, export memory behavior, cancellation, file-format capability reporting, and structured errors.

---

## 5. Mandatory repository protocol

The repository's `AGENTS.md` is normative. Before implementation, the executing agent must:

1. Inspect the repository root, Git status, dependency files, `run.sh`, `.protocol`, CI, and current tests.
2. Emit the repository's required `AGENT_PROTOCOL_HANDSHAKE` with every checkbox confirmed.
3. Copy this plan into:

   ```text
   docs/plans/2026-07-30-pyqt6-qscintilla-desktop-migration.md
   ```

4. Create a session log under `docs/agent_conversations/` using the repository's naming convention.
5. Use `./run.sh` for project commands so all caches and environments remain under `/tmp/wherewolf` as required.
6. Work on a feature branch. The default branch name for this plan is:

   ```text
   feat/pyqt6-desktop
   ```

7. Follow Red-Green-Refactor. Every phase below lists the behavior that must be tested before implementation.
8. Use atomic conventional commits. Do not put the entire migration into one unreviewable commit.
9. Never add placeholder tests, tests containing only `pass`, or tests that swallow all exceptions.
10. Run the full repository quality gate before each pull-request boundary:

    ```bash
    ./run.sh uv run ruff check . --fix
    ./run.sh uv run ruff format .
    ./run.sh uv run ty check src/
    ./run.sh uv run pytest
    ```

11. Record command output and unresolved deviations in the session log.

---

## 6. Locked product and technical decisions

These decisions are already made. The executing agent should not reopen them unless a verified technical or legal blocker is found.

| Decision | Selected approach |
|---|---|
| GUI framework | PyQt6, Qt Widgets |
| SQL editor | QScintilla via `PyQt6-QScintilla` |
| Project license for new release | `GPL-3.0-only`, after rights audit |
| Desktop architecture | `QMainWindow`, dock widgets, splitters, model/view tables |
| File selection | Native `QFileDialog.getOpenFileNames()` and `getSaveFileName()` |
| Browser/web content | None; do not use `QWebEngineView`, Ace, Monaco, or an embedded browser |
| Default engine | DuckDB |
| Spark | Optional dependency and lazy runtime |
| Query concurrency | One active query maximum |
| DuckDB lifecycle | New connection per execution and per schema task |
| Result display | Capped preview in a read-only `QTableView` |
| Result sorting | Local, type-aware preview sort; explicitly labelled as preview-only |
| Full-query ordering | Separate explicit action; never imply local preview sorting changed query semantics |
| SQL formatting | SQLGlot, same source dialect, one undo transaction |
| Completion | Wherewolf completion service plus QScintilla presentation adapter |
| Persistent UI settings | `QSettings` |
| Query history | Existing JSON location, migrated to an ID-based v2 schema |
| Streamlit migration | Temporary coexistence only; remove before release |
| Native installers | Deferred until after Python-package cutover |

---

## 7. Target architecture overview

### 7.1 Architectural rule

Qt widgets must not call DuckDB, Spark, SQLGlot translation, history storage, or export code directly. Widgets emit user intent. Controllers and services perform work. Worker objects return domain results. The GUI thread alone mutates Qt models and widgets.

### 7.2 Proposed source tree

The final structure should be close to the following. Minor naming adjustments are acceptable when they improve consistency, but responsibilities must remain separated.

```text
src/wherewolf/
├── __init__.py
├── __main__.py
├── cli.py
├── constants.py
├── domain/
│   ├── __init__.py
│   ├── enums.py
│   ├── errors.py
│   └── models.py
├── services/
│   ├── __init__.py
│   ├── catalog_service.py
│   ├── completion_service.py
│   ├── execution_service.py
│   ├── export_service.py
│   ├── formatting_service.py
│   ├── settings_service.py
│   └── statement_service.py
├── desktop/
│   ├── __init__.py
│   ├── application.py
│   ├── main_window.py
│   ├── actions.py
│   ├── query_controller.py
│   ├── resources.py
│   ├── dialogs/
│   │   ├── __init__.py
│   │   └── file_dialog_service.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── catalog_model.py
│   │   ├── polars_table_model.py
│   │   └── typed_sort_proxy_model.py
│   ├── widgets/
│   │   ├── __init__.py
│   │   ├── catalog_dock.py
│   │   ├── history_dock.py
│   │   ├── main_toolbar.py
│   │   ├── messages_panel.py
│   │   ├── result_table_view.py
│   │   ├── results_panel.py
│   │   ├── schema_panel.py
│   │   ├── sql_editor.py
│   │   └── translation_panel.py
│   └── workers/
│       ├── __init__.py
│       ├── execution_worker.py
│       └── schema_worker.py
├── execution/
│   ├── __init__.py
│   ├── base.py
│   ├── duckdb_engine.py
│   ├── registry.py
│   ├── spark_engine.py
│   └── spark_session.py
├── export/
│   ├── __init__.py
│   ├── clipboard.py
│   ├── duckdb_exporter.py
│   ├── preview_exporter.py
│   └── spark_exporter.py
├── storage/
│   ├── __init__.py
│   └── history.py
└── translation/
    ├── __init__.py
    └── translator.py
```

Do not create empty abstraction layers merely to match the tree. A module should exist only when it has a coherent responsibility and tests.

### 7.3 Runtime flow

```text
User action
    ↓
QAction / widget signal
    ↓
MainWindow or QueryController
    ↓
UI-neutral service creates immutable request
    ↓
ExecutionWorker on background thread
    ↓
Engine factory creates request-scoped engine resources
    ↓
QueryResult / SchemaResult / ExportResult
    ↓
Qt signal carrying a domain object
    ↓
GUI thread updates models, tabs, status, and history
```

### 7.4 State ownership

| State | Owner |
|---|---|
| Current SQL text and selection | `SqlEditor` |
| Catalog entries and aliases | `CatalogService`; mirrored by `CatalogModel` |
| Active execution state | `QueryController` |
| Current preview result | `ResultsPanel` / `PolarsTableModel` |
| Engine and dialect choice | main-window selection model and `QSettings` |
| History records | `HistoryRepository` |
| Window geometry, dock state, splitter sizes, theme, font, last directory | `SettingsService` over `QSettings` |
| Spark session | lazy `SparkSessionManager` |
| DuckDB connection | request-scoped engine instance |

No application behavior may depend on a global dictionary equivalent to `st.session_state`.

---

## 8. Core data structures

Use frozen, slotted dataclasses for immutable domain records. Use enums rather than string literals at service boundaries. Keep Qt types out of domain and service modules.

### 8.1 Enums

```python
from enum import Enum, StrEnum


class EngineKind(StrEnum):
    DUCKDB = "duckdb"
    SPARK = "spark"


class SourceFormat(StrEnum):
    CSV = "csv"
    PARQUET = "parquet"
    JSON = "json"
    JSON_LINES = "jsonl"
    XLSX = "xlsx"


class ExecutionStatus(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    CANCELLATION_REQUESTED = "cancellation_requested"
    SUCCEEDED = "succeeded"
    CANCELLED = "cancelled"
    FAILED = "failed"


class CompletionKind(StrEnum):
    TABLE = "table"
    CTE = "cte"
    COLUMN = "column"
    FUNCTION = "function"
    KEYWORD = "keyword"
    SNIPPET = "snippet"
```

The actual dialect type may remain a validated string if SQLGlot's supported dialect set is dynamic. Centralize the mapping between display names, SQLGlot names, DuckDB, and Spark SQL.

### 8.2 Catalog records

```python
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ColumnSchema:
    name: str
    data_type: str
    nullable: bool | None = None


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    id: UUID
    alias: str
    path: Path
    source_format: SourceFormat
    schema: tuple[ColumnSchema, ...] | None = None
    schema_error: str | None = None


@dataclass(frozen=True, slots=True)
class CatalogBinding:
    entry_id: UUID
    alias: str
    path: Path
    source_format: SourceFormat
```

`CatalogEntry` is live application state. `CatalogBinding` is the minimum immutable relation binding captured in an execution request.

### 8.3 Execution request and result

```python
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import polars as pl


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    request_id: UUID
    engine: EngineKind
    source_dialect: str
    original_sql: str
    executable_sql: str
    catalog: tuple[CatalogBinding, ...]
    preview_limit: int
    submitted_at: datetime


@dataclass(frozen=True, slots=True)
class QueryResult:
    request_id: UUID
    status: ExecutionStatus
    frame: pl.DataFrame | None
    execution_seconds: float
    preview_row_count: int
    total_row_count: int | None
    truncated: bool
    completed_at: datetime
    error_type: str | None = None
    error_message: str | None = None
    error_detail: str | None = None
```

Rules:

- `ExecutionRequest` is created once when Run is invoked.
- History and export refer to the request by ID and use its captured catalog and SQL.
- `preview_row_count` must not be presented as the total count when a limit was applied.
- `frame` is populated only for successful preview results.
- Errors are structured. A schema/import failure must not be represented as an empty successful DataFrame.

### 8.4 Schema and diagnostics

```python
@dataclass(frozen=True, slots=True)
class SchemaResult:
    entry_id: UUID
    columns: tuple[ColumnSchema, ...] | None
    error_type: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class SqlDiagnostic:
    message: str
    severity: str
    start_line: int
    start_column: int
    end_line: int | None = None
    end_column: int | None = None
```

### 8.5 Completion records

```python
@dataclass(frozen=True, slots=True)
class CompletionContext:
    sql: str
    cursor_offset: int
    dialect: str
    catalog: tuple[CatalogEntry, ...]


@dataclass(frozen=True, slots=True)
class CompletionItem:
    label: str
    insert_text: str
    kind: CompletionKind
    detail: str | None
    sort_key: tuple[int, str]
```

### 8.6 Export records

```python
@dataclass(frozen=True, slots=True)
class ExportRequest:
    export_id: UUID
    execution_request: ExecutionRequest
    destination: Path
    export_format: str
    scope: str  # "preview", "selection", or "full"
    include_headers: bool = True


@dataclass(frozen=True, slots=True)
class ExportResult:
    export_id: UUID
    destination: Path
    success: bool
    rows_written: int | None
    bytes_written: int | None
    error_message: str | None = None
```

---

## 9. Public interfaces

### 9.1 Execution engine protocol

```python
from typing import Protocol


class CancellationHandle(Protocol):
    @property
    def request_id(self) -> UUID: ...

    def cancel(self) -> bool:
        """Request cancellation. Return True when a cancellation signal was sent."""


class ExecutionEngine(Protocol):
    def execute_preview(self, request: ExecutionRequest) -> QueryResult: ...

    def inspect_schema(self, entry: CatalogEntry) -> SchemaResult: ...

    def export_full(self, request: ExportRequest) -> ExportResult: ...

    def cancellation_handle(self) -> CancellationHandle: ...

    def close(self) -> None: ...
```

An engine implementation must not import PyQt or Streamlit.

### 9.2 Engine registry

```python
class EngineRegistry:
    def available_engines(self) -> tuple[EngineDescriptor, ...]: ...

    def create(self, kind: EngineKind, request_id: UUID) -> ExecutionEngine: ...
```

The registry must not import PySpark merely to render the engine selector. Spark availability detection must be lazy and side-effect-free.

### 9.3 Catalog service

```python
class CatalogService:
    def add_paths(self, paths: Sequence[Path]) -> tuple[CatalogEntry, ...]: ...
    def remove(self, entry_id: UUID) -> None: ...
    def rename(self, entry_id: UUID, alias: str) -> CatalogEntry: ...
    def update_schema(self, result: SchemaResult) -> CatalogEntry: ...
    def entries(self) -> tuple[CatalogEntry, ...]: ...
    def snapshot(self) -> tuple[CatalogBinding, ...]: ...
```

Requirements:

- Resolve paths before duplicate checks.
- Deduplicate by resolved path.
- Generate valid aliases from filenames.
- Enforce case-insensitive uniqueness using `casefold()`.
- Use deterministic suffixes (`orders`, `orders_2`, `orders_3`).
- Reject an empty or invalid user rename with an actionable message.
- Keep user-facing aliases distinct from generated internal engine relation IDs.

### 9.4 Formatting service

```python
class SqlFormattingService:
    def format(self, sql: str, dialect: str) -> FormattingResult: ...
```

`FormattingResult` contains either formatted SQL or diagnostics. The service must never mutate editor text and must never translate to another dialect.

### 9.5 Completion service

```python
class SqlCompletionService:
    def complete(self, context: CompletionContext) -> tuple[CompletionItem, ...]: ...
    def call_tip(self, context: CompletionContext) -> str | None: ...
```

The service is deterministic and independently unit-testable. QScintilla popup details belong in a separate adapter.

### 9.6 History repository

```python
class HistoryRepository:
    def list_recent(self, limit: int = 100) -> tuple[HistoryRecord, ...]: ...
    def append(self, record: HistoryRecord) -> None: ...
    def get(self, record_id: UUID) -> HistoryRecord | None: ...
    def clear(self) -> None: ...
```

Display labels must never be used as record identities.

### 9.7 File dialog abstraction

```python
class FileDialogService(Protocol):
    def choose_dataset_files(self, parent: object, start_dir: Path) -> tuple[Path, ...]: ...
    def choose_export_path(
        self,
        parent: object,
        start_dir: Path,
        suggested_name: str,
        export_format: str,
    ) -> Path | None: ...
```

The production adapter calls `QFileDialog`; tests inject a fake. Automated tests must never open a native modal dialog.

---

## 10. Desktop user interface specification

### 10.1 Main window

Use `QMainWindow` with:

- menu bar;
- primary query toolbar;
- left dataset catalog dock;
- optional right query-history dock;
- central vertical splitter containing the SQL editor and output tabs;
- status bar.

Recommended layout:

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ File  Edit  Query  View  Help                                            │
├──────────────────────────────────────────────────────────────────────────┤
│ [Add files] [Run] [Cancel] [Format SQL]  Engine [DuckDB ▼] Dialect [...] │
├──────────────────────┬───────────────────────────────────────────────────┤
│ Datasets             │ SQL editor                                        │
│                      │                                                   │
│ orders               │ SELECT ...                                        │
│ customers            │                                                   │
│ events               ├───────────────────────────────────────────────────┤
│                      │ Results | Schema | Translation | Messages          │
│ [+ Add files]        │                                                   │
├──────────────────────┴───────────────────────────────────────────────────┤
│ DuckDB · 1,000 preview rows · 0.042 s · Truncated · Sorted preview only │
└──────────────────────────────────────────────────────────────────────────┘
```

### 10.2 Menus and actions

Create each command once as a `QAction`. Reuse the same action in menus, toolbars, context menus, and shortcuts.

#### File

- Add Datasets… — `Ctrl+O` / `Cmd+O`
- Remove Selected Dataset
- Export Preview…
- Export Full Result…
- Preferences…
- Quit

#### Edit

- Undo
- Redo
- Cut
- Copy
- Paste
- Select All
- Find…
- Replace…
- Toggle Comment

#### Query

- Run Selection or Current Statement — `Ctrl+Enter` / `Cmd+Enter`
- Cancel Query — `Ctrl+.` / `Cmd+.`
- Format SQL — `Ctrl+Shift+F` on Windows/Linux and `Cmd+Shift+F` on macOS
- Show Completion — `Ctrl+Space`
- Translate SQL
- Clear Editor

#### View

- Dataset Catalog
- Query History
- Results/Schema/Translation/Messages tabs
- Reset Layout
- Increase Editor Font
- Decrease Editor Font
- System / Light / Dark theme

#### Help

- Documentation
- About Wherewolf
- Open-Source Licenses

Use `QKeySequence.StandardKey` for standard commands. Store non-standard shortcuts in preferences and allow future rebinding.

### 10.3 Status bar

The status bar must show:

- selected engine;
- execution state;
- elapsed time;
- preview row count;
- truncated state;
- local sort/filter state;
- transient success/error messages.

Do not report a preview row count as a total row count.

### 10.4 Persistent layout

Use `QSettings` to save and restore:

- main-window geometry;
- dock layout and visibility;
- splitter positions;
- last dataset directory;
- last export directory;
- engine and source dialect;
- preview limit;
- editor font family and size;
- theme;
- completion settings;
- configurable shortcuts.

The application must recover safely from corrupt or obsolete settings by resetting only the affected values.

### 10.5 Styling

- Use the operating-system style by default.
- Keep application QSS minimal.
- Do not reproduce the Streamlit CSS approach.
- Use Qt standard icons or project-owned GPL-compatible SVG assets. Record third-party asset licenses if any are introduced.
- Ensure keyboard focus indicators remain visible.
- Assign accessible names to icon-only controls.

---

## 11. Native file and dataset catalog behavior

### 11.1 Open dialog

The Add Datasets action calls the production `FileDialogService`, which uses `QFileDialog.getOpenFileNames()` with native dialogs enabled.

Supported filters at cutover:

```text
Data files (*.csv *.parquet *.json *.jsonl *.xlsx)
CSV files (*.csv)
Parquet files (*.parquet)
JSON files (*.json *.jsonl)
Excel workbooks (*.xlsx)
All files (*)
```

Do not advertise `.xls` until a tested legacy Excel reader is deliberately added. Existing `.xls` claims must be removed from constants, README, UI filters, and tests.

### 11.2 Drag and drop

The main window and dataset catalog accept local-file URL drops. Requirements:

- accept multiple files;
- reject directories unless directory import is separately implemented later;
- ignore unsupported paths with a consolidated warning;
- deduplicate against existing catalog paths;
- use the same catalog-add path as the native dialog;
- do not duplicate alias-validation logic in the widget.

### 11.3 Catalog presentation

Use a `QTreeView` or `QTableView` backed by `CatalogModel`. Minimum columns:

- Alias
- File
- Format
- Schema status

The path should be visible in a tooltip and in a details area, not forced into a wide column.

### 11.4 Catalog actions

Right-click and keyboard actions:

- Rename Alias
- Remove
- Refresh Schema
- Copy Alias
- Copy File Path
- Insert Alias at Editor Cursor
- Reveal in Finder / Explorer / file manager, where supported

Double-clicking the alias begins inline rename. Double-clicking a column in the schema panel inserts the appropriately quoted column name into the editor.

### 11.5 Schema loading

- Add catalog entries immediately.
- Load schema asynchronously.
- Mark entries as Loading, Ready, or Error.
- A schema error must show its real error, not “no columns detected.”
- Retrying schema inspection must be possible.
- Schema completion data updates only after the GUI thread receives a `SchemaResult`.

### 11.6 File-format semantics

- `.jsonl` is explicitly newline-delimited JSON.
- `.json` is treated as conventional JSON, including multiline/top-level arrays where supported.
- Spark JSON loading must set appropriate multiline behavior for `.json` and normal line-delimited behavior for `.jsonl`.
- `.xlsx` remains supported through the tested engine/import path.
- Capabilities must be engine-specific. The UI must not claim a format for an engine that cannot actually read it.

---

## 12. SQL editor specification

### 12.1 Base widget

Implement `SqlEditor` as a subclass or composition wrapper around `QsciScintilla`.

Required baseline features:

- SQL syntax highlighting;
- line-number margin;
- current-line highlight;
- brace matching;
- sensible tab and indentation behavior;
- automatic indentation;
- undo/redo;
- cut/copy/paste;
- find and replace;
- configurable monospace font and size;
- light and dark palettes;
- selection execution;
- current-statement execution;
- completion popup;
- function call tips;
- parse-error indicator and message;
- comment/uncomment shortcut;
- automatic closing of parentheses and quotes only when it does not interfere with selection replacement.

Use `QsciLexerSQL` initially, subclassing or extending its keyword sets for DuckDB and Spark-specific words. Do not build a custom lexer unless tests demonstrate that the built-in lexer cannot meet the acceptance criteria.

### 12.2 Statement selection and execution

The Run action follows this deterministic policy:

1. If the editor has a non-empty selection, execute the selected text.
2. Otherwise, locate the SQL statement containing the cursor and execute that statement.
3. If the document contains exactly one statement, execute the document.
4. If no unambiguous statement can be identified, show an error instead of silently discarding statements.

The current translator's “return the first transpiled statement” behavior must not survive this migration. The statement service must preserve or explicitly reject every statement.

Implement a quote/comment-aware statement locator. A semicolon inside a string or comment must not split a statement.

### 12.3 Completion / IntelliSense architecture

Do not rely solely on QScintilla's static API list. Build a Wherewolf-specific completion service and a thin QScintilla adapter.

Completion sources:

1. SQL keywords for the selected source dialect.
2. Engine/dialect functions and their signatures.
3. Current catalog aliases.
4. Known columns from cached catalog schemas.
5. Aliases declared in the current statement.
6. CTE names and, when derivable, CTE columns.
7. Result aliases in contexts such as `ORDER BY`.
8. Useful SQL snippets.

Completion contexts:

| Cursor context | Priority suggestions |
|---|---|
| After `FROM` or `JOIN` | catalog aliases and CTEs |
| After `alias.` | only columns belonging to that alias |
| `SELECT`, `WHERE`, `GROUP BY`, `HAVING`, `ORDER BY` | in-scope columns, functions, result aliases as appropriate |
| Function name prefix | matching dialect functions |
| Empty/general context | keywords, snippets, catalog aliases |
| Inside a string or comment | no automatic popup |

Completion ranking order:

1. exact case-insensitive prefix match;
2. resolved `alias.` column;
3. in-scope table/CTE;
4. unambiguous in-scope column;
5. function;
6. keyword;
7. fuzzy match.

Rules:

- Automatic completion begins after a configurable threshold, default two characters.
- `Ctrl+Space` forces completion even with an empty prefix.
- The completion service must remain useful when SQL is incomplete and SQLGlot cannot parse it. Use a fast lexical/token fallback.
- When a statement parses, use SQLGlot AST information to improve alias, CTE, and scope resolution.
- Never block the GUI thread on schema inspection. Use cached metadata only and schedule missing schema work separately.
- Insert appropriately quoted identifiers when a name requires quoting.
- Function completion may insert `function_name(` and trigger a call tip.
- Visually distinguish tables, CTEs, columns, functions, keywords, and snippets. Use QScintilla autocomplete type metadata/images or an equivalent tested mechanism.
- Completion results should normally appear within 100 ms when metadata is already cached. Treat this as a target, not a test that fails on slow CI hardware.

Minimum cutover completion cases:

```sql
SELECT *
FROM <cursor>
```

must suggest catalog aliases.

```sql
SELECT o.<cursor>
FROM orders AS o
```

must suggest only `orders` columns.

```sql
SELECT *
FROM orders o
JOIN customers c
  ON o.customer_id = c.<cursor>
```

must prioritize `customers` columns.

### 12.4 SQL formatting

Create one shared Format SQL `QAction` available from:

- the primary toolbar;
- Query → Format SQL;
- the editor context menu;
- `Ctrl+Shift+F` on Windows/Linux;
- `Cmd+Shift+F` on macOS.

Formatting policy:

1. If text is selected, format the selection only.
2. Otherwise, format the current statement.
3. If the document contains a single statement, format the entire document.
4. Formatting uses the selected source dialect for both parsing and generation.
5. Formatting must not transpile to the execution engine's dialect.
6. Preserve whether the formatted region ended with a semicolon.
7. Preserve the document's line-ending convention.
8. Apply the replacement inside one QScintilla undo action using `beginUndoAction()` and `endUndoAction()`.
9. Restore the cursor, selection, first visible line, and horizontal scroll position as closely as practical.
10. On parse failure, leave the text byte-for-byte unchanged, show a message, and place an editor indicator at the best available line/column.
11. Do not silently drop additional statements.
12. Formatting comments is best-effort, but comment-loss regressions covered by tests are release blockers.

Use SQLGlot's parser and pretty-printer through a UI-neutral `SqlFormattingService`.

Suggested result type:

```python
@dataclass(frozen=True, slots=True)
class FormattingResult:
    formatted_sql: str | None
    diagnostics: tuple[SqlDiagnostic, ...]
```

### 12.5 Editor context menu

Add:

- Undo / Redo
- Cut / Copy / Paste
- Run Selection or Current Statement
- Format SQL
- Show Completion
- Toggle Comment
- Insert Dataset Alias submenu
- Insert Column submenu for the currently focused dataset

---

## 13. Result table specification

### 13.1 Model/view implementation

Use:

- `QTableView` for presentation;
- `PolarsTableModel(QAbstractTableModel)` for data;
- `TypedSortProxyModel(QSortFilterProxyModel)` for local preview sorting/filtering;
- a custom `ResultTableView` for selection, clipboard, headers, context menus, and shortcuts.

Do not use `QTableWidget`. Do not create a QWidget per cell.

The model is read-only and lives on the GUI thread. A worker may construct a Polars DataFrame, but the Qt model is populated only after the result signal reaches the GUI thread.

### 13.2 Model roles

At minimum:

- `DisplayRole`: formatted human-readable value;
- custom raw-value role: Python/Polars scalar for sorting and copying;
- original-row role: source preview position for restoring query order;
- `ToolTipRole`: full untruncated value and type where useful;
- `TextAlignmentRole`: numeric right alignment, text left alignment;
- `ForegroundRole` or font treatment for nulls, without relying on color alone.

Null display defaults:

- table display: `NULL` or a muted `null` token, configurable;
- spreadsheet copy: blank by default;
- SQL-value copy: `NULL`.

### 13.3 Selection

Configure extended item selection. Support:

- single-cell selection;
- rectangular range selection;
- Shift expansion;
- Ctrl/Cmd discontiguous selection;
- full-row selection through the vertical header;
- full-column selection through the horizontal header;
- `Ctrl+A` / `Cmd+A` for all preview cells.

Selection must remain usable after local sorting and visual column reordering.

### 13.4 Clipboard behavior

`Ctrl+C` / `Cmd+C` copies selected cells in current visual row and column order as tab-separated text suitable for spreadsheet paste.

Use a standards-aware serializer so embedded tabs, line breaks, quotes, dates, decimals, booleans, and nulls are deterministic.

For a discontiguous selection, serialize the bounding rectangle and leave unselected positions blank. Document and test this behavior.

Context-menu commands:

- Copy
- Copy with Column Names
- Copy as CSV
- Copy as SQL Values
- Copy Selected Rows
- Export Selection…

Suggested shortcut:

- Copy with Column Names — `Ctrl+Shift+C` / `Cmd+Shift+C`

### 13.5 Column-header actions

Right-clicking a column header provides:

- Copy Column Name
- Copy Quoted Column Name
- Copy All Visible Column Names
- Copy Selected Column Names
- Insert Column Name into Editor
- Insert Quoted Column Name into Editor
- Hide Column
- Show Hidden Columns submenu
- Auto-size This Column
- Auto-size All Columns
- Reset Column Widths
- Reset Column Order
- Clear Preview Sort

Identifier quoting uses the active execution engine's rules, not naive string concatenation.

### 13.6 Sorting

Header clicks implement a three-state cycle:

1. ascending;
2. descending;
3. original query order.

Sorting must be type-aware. Numeric, boolean, date, datetime, duration, and string values must not be compared only through their display strings. Define and test null ordering.

The status bar must display **“Sorted preview only”** whenever a local sort is active.

A local preview sort must never change the captured execution request or full export order.

### 13.7 Full-query ordering

Provide a separate explicit action, initially through the column-header context menu:

- Apply Ascending Order to Query
- Apply Descending Order to Query

Behavior:

1. Use SQLGlot to wrap the current executable statement safely:

   ```sql
   SELECT *
   FROM (
       <original statement>
   ) AS _wherewolf_result
   ORDER BY <quoted column> ASC|DESC
   ```

2. Put the generated SQL into the editor or a preview dialog before execution.
3. Do not silently modify and rerun SQL when a user merely clicks a header.
4. If the output column cannot be referenced safely, disable the action with an explanatory tooltip.

This action may be delivered after basic local sorting but is required before calling the result grid feature-complete.

### 13.8 Column layout

Enable:

- drag-to-reorder columns;
- manual resize;
- double-click auto-size;
- hide/show columns;
- reset to query order.

Visual reordering affects display and clipboard output. It does not mutate the underlying DataFrame or SQL unless the user explicitly chooses a query-edit action.

### 13.9 Preview search/filter

Provide a lightweight search bar for the loaded preview:

- `Ctrl+F` / `Cmd+F` focuses it when the result grid has focus;
- case-insensitive substring search by default;
- optional column scope;
- visible indication that filtering applies only to the loaded preview;
- Clear action restores all preview rows.

---

## 14. Query execution, threading, and cancellation

### 14.1 State machine

`QueryController` owns this state machine:

```text
IDLE
  └── Run → RUNNING
RUNNING
  ├── completed → SUCCEEDED → IDLE
  ├── error → FAILED → IDLE
  └── Cancel → CANCELLATION_REQUESTED
CANCELLATION_REQUESTED
  ├── worker confirms cancellation → CANCELLED → IDLE
  ├── query completes before interrupt → SUCCEEDED → IDLE
  └── cancellation fails/query errors → FAILED → IDLE
```

Rules:

- Disable Run while a request is active.
- Enable Cancel only while Running or Cancellation Requested.
- A Cancel click changes the UI to “Cancellation requested”; it does not claim success immediately.
- Do not clear the active request until a terminal worker signal is received.
- Ignore stale terminal signals whose request ID does not match the controller's active request.
- The app must remain responsive while a query or export runs.

### 14.2 Worker model

Use a dedicated background execution worker for the one active query. Either of these is acceptable after a prototype test:

- a `QObject` moved to a dedicated `QThread`; or
- a `QRunnable` in a `QThreadPool` capped at one execution task.

The selected implementation must satisfy cancellation. A cancel operation cannot depend on a queued slot in the same blocked event loop as the running query.

Recommended design:

1. Worker creates the engine and publishes a thread-safe `CancellationHandle` to the controller.
2. Controller calls the handle directly when Cancel is requested.
3. Worker emits a terminal result when the engine call returns.
4. Worker closes request-scoped resources in `finally`.
5. GUI models are updated only in GUI-thread slots.

Use `pyqtSignal(object)` or strongly typed wrappers for domain objects. Do not pass widgets into workers.

### 14.3 DuckDB execution

Refactor DuckDB to:

- create a new connection for every query execution;
- create a new connection for every schema-inspection task;
- register the immutable catalog snapshot on that connection;
- use generated internal relation IDs to avoid stale global views;
- expose a cancellation handle that interrupts only the current connection;
- close the connection in `finally`;
- preserve the current safe-preview behavior by requesting `preview_limit + 1` rows and setting `truncated` when the extra row exists;
- return a structured `QueryResult` for success, cancellation, and failure.

No DuckDB connection may be cached in Qt global state.

### 14.4 Spark execution

Refactor Spark to:

- import PySpark only when the Spark engine is requested;
- create/start the Spark session lazily in a background task;
- reuse one local Spark context for the single application instance;
- use a new SQL session or isolated request namespace as appropriate;
- assign a request-specific job group using the execution request ID;
- cancel only that job group;
- never use `cancelAllJobs()` for the normal Cancel action;
- create and drop request-specific temporary views;
- return structured errors if Java or Spark is unavailable;
- avoid starting Spark during normal DuckDB startup or tests.

### 14.5 Execution snapshot

When Run is invoked, capture:

- original SQL;
- statement/selection actually chosen;
- source dialect;
- translated executable SQL;
- selected engine;
- exact catalog alias/path/format bindings;
- preview limit;
- request ID and submission time.

History and full export must refer to this snapshot. They must not read mutable current UI values after the run.

### 14.6 Translation

- Translate exactly the statement selected for execution.
- Raise on unsupported translation rather than silently returning a best-effort first statement with omitted statements.
- Store both original and executable SQL in the request.
- Show translated SQL in a read-only panel with Copy and Replace Editor actions.
- Translation errors prevent execution and appear as editor/messages diagnostics.

---

## 15. Schema, translation, messages, and metrics panels

Use a bottom `QTabWidget` containing:

1. Results
2. Schema
3. Translation
4. Messages

### 15.1 Results

Contains the `ResultTableView`, preview search, export actions, and preview-state banner.

### 15.2 Schema

Show schema for:

- the focused catalog entry; or
- the current result, when result metadata is available.

Columns:

- Name
- Type
- Nullable, when known

Actions:

- Copy name
- Copy quoted name
- Insert into editor
- Refresh

### 15.3 Translation

Read-only QScintilla or plain-text SQL view with:

- source dialect;
- target engine dialect;
- translated SQL;
- Copy;
- Replace Editor;
- Format display.

Do not update the editor automatically merely because translation exists.

### 15.4 Messages

Show:

- parse and translation diagnostics;
- import/schema errors;
- engine errors;
- cancellation result;
- export messages;
- non-sensitive debug correlation ID where useful.

The default user message should be concise. Full exception details can be expandable or copied for bug reports.

### 15.5 Metrics

Display:

- engine;
- elapsed time;
- preview rows;
- truncation;
- optional total rows only when actually calculated;
- request ID in a copyable details view.

---

## 16. History and settings

### 16.1 History schema v2

Continue using `~/.wherewolf/history.json` for this single-user tool, but migrate records to an explicit schema:

```json
{
  "schema_version": 2,
  "records": [
    {
      "id": "uuid",
      "submitted_at": "ISO-8601",
      "completed_at": "ISO-8601",
      "status": "succeeded",
      "engine": "duckdb",
      "source_dialect": "duckdb",
      "original_sql": "SELECT ...",
      "executable_sql": "SELECT ...",
      "catalog": [
        {
          "alias": "orders",
          "path": "/absolute/path/orders.parquet",
          "format": "parquet"
        }
      ],
      "preview_row_count": 1000,
      "truncated": true,
      "execution_seconds": 0.42,
      "error_message": null
    }
  ]
}
```

Requirements:

- assign every entry a UUID;
- use UUIDs for selection and retrieval;
- preserve existing v1 history through a tested migration;
- validate types while loading;
- skip or quarantine malformed individual records rather than losing the entire file;
- use atomic write/replace;
- cap records according to an explicit setting;
- never identify a record by a truncated query label.

### 16.2 History UI

A dockable history list shows:

- time;
- engine;
- status;
- first meaningful SQL line.

Actions:

- Restore SQL
- Restore Catalog
- Restore SQL and Catalog
- Copy SQL
- Delete Entry
- Clear History

When restoring catalog entries, missing files are shown as missing and are not silently removed.

### 16.3 QSettings

Use a stable organization/application pair, for example:

```python
QCoreApplication.setOrganizationName("Wherewolf")
QCoreApplication.setApplicationName("Wherewolf")
```

Version settings keys. Do not store query history in `QSettings`.

---

## 17. Export architecture

### 17.1 Principles

- Use a native save dialog.
- Export to a filesystem path, not to a byte blob retained in UI state.
- Capture or reuse the original `ExecutionRequest`.
- Write to a temporary sibling path and atomically replace the destination after success where the format permits.
- Confirm overwrite.
- Run full exports off the GUI thread.
- Support cancellation.
- Surface real errors.
- Do not claim that a full export matches the preview if catalog or source files have changed. The execution snapshot should include source path, size, and modification time where practical, and the UI should warn if these differ.

### 17.2 Export scopes

#### Preview

Export the currently loaded preview DataFrame. This is bounded and may use Polars/XlsxWriter helpers.

#### Selection

Serialize only selected visual rows/columns, respecting sort, filter, and column order.

#### Full result

Rerun the captured execution request without the preview limit and stream/write directly to the chosen path.

### 17.3 DuckDB full export

Preferred paths:

- CSV: DuckDB `COPY (<query>) TO <temp-path>` with tested options.
- Parquet: DuckDB `COPY (<query>) TO <temp-path> (FORMAT PARQUET)`.
- XLSX: stream batches to XlsxWriter in constant-memory mode or enforce a documented bound. Do not build a complete Polars DataFrame and a second byte copy.

All destination SQL literals must use one tested escaping helper. Never interpolate an unescaped path.

### 17.4 Spark full export

For CSV and Parquet:

- use Spark's DataFrame writer into a temporary directory;
- for the local single-user UX, produce a single output artifact through a deliberate, documented coalesce/part-file strategy;
- move the completed part file to the requested destination;
- clean temporary directories on success, failure, and startup recovery.

For XLSX:

- use a bounded driver-side batch path only;
- show an explicit size/row guard;
- fail safely rather than exhausting driver memory.

### 17.5 Export naming

Suggested filenames use:

```text
wherewolf-YYYYMMDD-HHMMSS.<ext>
```

Do not derive unsafe filenames from arbitrary SQL text.

### 17.6 Export UI

The Results panel provides:

- Export Preview…
- Export Selection…
- Export Full Result…

A full export shows status and permits cancellation. The application must remain usable for viewing the existing preview while export runs, but query execution remains disabled if the implementation shares the single worker/engine resource.

---

## 18. Dependency and packaging plan

### 18.1 Runtime dependencies

Add:

- `PyQt6`
- `PyQt6-QScintilla`

Remove after cutover:

- `streamlit`
- `streamlit-ace`

Move to optional extra:

- `pyspark`
- any dependency needed only for Spark and not by the DuckDB/Polars path

Retain only dependencies verified as required by the default desktop application.

Suggested shape, with exact compatible versions resolved by `uv` during Phase 0:

```toml
[project]
dependencies = [
    "duckdb>=1.5,<2",
    "fastexcel>=0.20,<1",
    "polars>=1.41,<2",
    "pyarrow>=24,<25",  # retain only if default-path tests prove it is required
    "PyQt6>=6.8,<7",
    "PyQt6-QScintilla>=2.14,<3",
    "sqlglot>=30,<31",
    "xlsxwriter>=3.2,<4",
]

[project.optional-dependencies]
spark = [
    "pyspark>=4.1,<5",
]
```

Do not copy these ranges blindly. The dependency spike must resolve and test a compatible set on supported Python versions and then update the lockfile.

### 18.2 Development dependencies

Add:

- `pytest-qt`

Remove Playwright if no non-Qt tests still require it after Streamlit removal.

### 18.3 Entry points

During migration:

```toml
[project.scripts]
wherewolf = "wherewolf.cli:main"                 # existing Streamlit until cutover
wherewolf-desktop = "wherewolf.desktop.application:main"
```

At cutover:

```toml
[project.scripts]
wherewolf = "wherewolf.desktop.application:main"
```

Remove the temporary `wherewolf-desktop` command after one release unless there is a documented compatibility reason to retain it.

Add `src/wherewolf/__main__.py` so this works:

```bash
python -m wherewolf
```

### 18.4 Startup requirements

- Importing `wherewolf.desktop.application` must not import PySpark.
- Launching the DuckDB application must not start Java or Spark.
- Application version comes from installed package metadata with one consistent development fallback.
- Cleanly report missing optional Spark support in the engine selector and documentation.

### 18.5 Initial distribution

Release the Qt application as a standard wheel/source distribution through the existing package workflow first. Evaluate standalone installers only after `1.0.0` stabilizes.

---

## 19. Licensing plan and merge gate

### 19.1 Gate

Before merging PyQt6/QScintilla application code, establish that the maintainer can relicense all relevant code.

The executing agent must produce a brief rights-audit note containing:

- `git shortlog -sne --all` output;
- a list of non-maintainer contributors, if any;
- identification of copied/vendor-derived code and its license;
- confirmation from the maintainer that all necessary copyrights are owned or permissions have been obtained.

If authority is not established, stop the relicensing portion and report the blocker. Do not silently substitute a different license or framework.

### 19.2 Relicensing changes

After the gate passes:

1. Replace the root `LICENSE` with the full GPL version 3 text.
2. Use SPDX identifier `GPL-3.0-only` in project metadata.
3. Update package classifiers and README license sections.
4. Add a `NOTICE.md` or `LICENSES/MIT-pre-1.0.txt` explaining that versions released before the relicense remain available under their original MIT terms.
5. Preserve copyright notices.
6. Add an About → Open-Source Licenses view listing Wherewolf, PyQt6, QScintilla, Qt, DuckDB, SQLGlot, Polars, Spark when installed, and other distributed components.
7. Review any icons or bundled resources for compatible licenses.
8. Update contribution documentation so new contributions are knowingly made under GPL-3.0-only.

The project cannot revoke MIT rights already granted for earlier published code. The documentation must not imply otherwise.

### 19.3 Versioning

Use `1.0.0` for the cutover because the release changes:

- application architecture and launch behavior;
- dependency and packaging profile;
- user interface;
- licensing terms for new releases.

Do not bump the version until the final cutover phase.

---

## 20. Detailed implementation phases

Each phase follows this order:

1. write or update tests and observe failure;
2. implement the minimum correct behavior;
3. refactor while tests remain green;
4. run phase tests plus the existing suite;
5. update the session log;
6. commit atomically.

### Phase 0 — Baseline, protocol, rights audit, and dependency spike

**Purpose:** establish a reproducible baseline and prove the chosen Qt stack works before architecture changes.

#### Red / verification work

- Run the repository handshake required by `AGENTS.md`.
- Run all current checks through `./run.sh` and record baseline failures, if any.
- Add a temporary dependency-spike test or script that:
  - imports PyQt6;
  - imports `PyQt6.Qsci`;
  - creates a `QApplication` under `QT_QPA_PLATFORM=offscreen`;
  - creates and destroys a `QsciScintilla` widget;
  - exits without starting Streamlit.
- Run the spike on Python 3.11 and 3.12 locally/CI where possible.
- Complete the rights audit described in Section 19.

#### Implementation

- Copy this plan into `docs/plans/`.
- Create the session log.
- Create an architecture decision record if the repository uses ADRs; otherwise add a short decision section to this plan's implementation notes.
- Resolve compatible PyQt6/QScintilla/pytest-qt versions with `uv` in the feature branch.
- Do not yet remove Streamlit.

#### Exit criteria

- Baseline is documented.
- QScintilla can instantiate headlessly.
- Rights audit is approved by the maintainer.
- Compatible dependency versions are locked.

#### Suggested commit

```text
docs: record PyQt6 desktop migration and license audit
```

### Phase 1 — Relicense future releases

**Purpose:** make the repository's distribution terms compatible with the selected GPL-only Python bindings before product code depends on them.

#### Red / verification work

- Add metadata tests asserting the expected SPDX license and classifiers.
- Add a documentation test or simple repository assertion that the old MIT notice is retained for pre-cutover releases.

#### Implementation

- Replace/update license files and notices.
- Update `pyproject.toml`, README, and contribution language.
- Add an initial open-source notices document.

#### Exit criteria

- License metadata, files, and README agree on `GPL-3.0-only`.
- Pre-cutover MIT status is accurately documented.
- The rights audit is referenced in the session log.

#### Suggested commit

```text
chore!: relicense future Wherewolf releases under GPL-3.0-only
```

### Phase 2 — UI-neutral domain contracts and engine registry

**Purpose:** remove Streamlit state from the core execution contract while the old UI still runs.

#### Red

Add unit tests for:

- immutable `ExecutionRequest` snapshots;
- catalog path and alias snapshot isolation;
- structured success/error/cancelled results;
- engine registry availability without importing PySpark;
- case-insensitive alias collisions;
- statement selection that does not discard later statements.

#### Implementation

- Add domain enums/models/errors.
- Add `ExecutionEngine` and cancellation protocols.
- Replace `engines.py` Streamlit cache functions with `execution/registry.py` or an equivalent UI-neutral factory.
- Adapt old Streamlit code temporarily through a compatibility adapter if needed.
- Extend translation to operate on explicit selected statements.

#### Exit criteria

- Core modules import without Streamlit.
- Request data does not change when the live catalog changes.
- Existing engine tests remain green through compatibility adapters.

#### Suggested commit

```text
refactor: introduce immutable execution and engine contracts
```

### Phase 3 — PyQt6 application shell and temporary desktop entry point

**Purpose:** establish a native window and testable command path without query behavior.

#### Red

Using `pytest-qt`, add tests that:

- `wherewolf-desktop` creates one `QMainWindow`;
- the expected menus and actions exist;
- Run and Cancel initial enabled states are correct;
- geometry/settings restoration tolerates invalid settings;
- closing the window exits cleanly.

#### Implementation

- Add `desktop/application.py`, `main_window.py`, and `actions.py`.
- Add the temporary `wherewolf-desktop` script.
- Build the dock/splitter/tab layout.
- Add system theme and minimal settings persistence.
- Add placeholder panels only where they are real widgets with tests; do not add empty production stubs that masquerade as features.

#### Exit criteria

- Native window launches without browser or Streamlit server.
- Headless Qt smoke test passes.
- Window geometry and layout persist.

#### Suggested commit

```text
feat(desktop): add native PyQt6 application shell
```

### Phase 4 — Dataset catalog, native dialogs, and drag/drop

**Purpose:** replace the custom filesystem browser.

#### Red

Tests for:

- multi-path dialog result handling through a fake dialog service;
- no-op on dialog cancellation;
- duplicate resolved paths;
- alias sanitization and `casefold()` uniqueness;
- unsupported extension reporting;
- drag/drop URL handling;
- catalog rename/remove actions;
- last-directory persistence;
- `.xls` rejection and `.xlsx` acceptance.

#### Implementation

- Add `FileDialogService` production/fake interfaces.
- Add `CatalogService`, `CatalogModel`, and `CatalogDock`.
- Add native Add Datasets action and file filters.
- Add local-file drag/drop.
- Add context menu and inline rename.
- Schedule schema tasks but defer full schema panel wiring until Phase 10.

#### Exit criteria

- User can add several files through the native dialog.
- User can drag files into the app.
- Custom browser is no longer needed by the desktop path.
- Catalog behavior is fully unit-tested without opening native dialogs.

#### Suggested commit

```text
feat(desktop): add native dataset catalog and file dialogs
```

### Phase 5 — QScintilla editor foundation

**Purpose:** replace Ace's basic editing experience before adding semantic features.

#### Red

Tests for:

- editor creation under `pytest-qt`;
- SQL lexer assigned;
- line-number margin visible;
- Run action uses selected text;
- current-statement locator respects quoted semicolons and comments;
- find/replace;
- toggle comment;
- font/theme settings;
- keyboard action dispatch.

#### Implementation

- Add `SqlEditor`.
- Configure QScintilla margins, lexer, brace matching, indentation, caret line, and selection behavior.
- Add statement service and selection/current-statement command.
- Add standard edit actions and editor context menu.

#### Exit criteria

- Editor provides syntax highlighting and expected desktop editing behavior.
- Selected/current statement can be obtained deterministically without execution.

#### Suggested commit

```text
feat(editor): add QScintilla SQL editing foundation
```

### Phase 6 — SQL formatting action and diagnostics

**Purpose:** deliver the explicitly requested formatting button and hotkey.

#### Red

Unit tests for:

- same-dialect parse/generate;
- selected-region formatting;
- current-statement formatting;
- whole-document formatting for a single statement;
- multiple statements retained;
- trailing semicolon preservation;
- line-ending preservation;
- strings and comments;
- quoted identifiers;
- dialect-specific syntax;
- parse error returns diagnostics and unchanged text.

Widget tests for:

- toolbar/menu/context action all invoke the same `QAction`;
- platform shortcut is assigned;
- formatting is undone with one Undo command;
- cursor/scroll restoration is within defined bounds;
- parse error creates an indicator and does not alter editor text.

#### Implementation

- Add `SqlFormattingService`.
- Wire Format SQL action.
- Add diagnostic indicator ranges and Messages-panel event.
- Persist configurable shortcut.

#### Exit criteria

- Format SQL works from button, menu, context menu, and shortcut.
- One Undo restores the entire pre-format state.
- Failure is non-destructive.

#### Suggested commit

```text
feat(editor): add dialect-aware SQL formatting action
```

### Phase 7 — Schema-aware completion and call tips

**Purpose:** match and improve Ace autocomplete.

#### Red

Unit tests for completion contexts:

- `FROM` suggests catalog aliases;
- `JOIN` suggests aliases and CTEs;
- `alias.` suggests only resolved columns;
- unqualified column ranking;
- CTE names;
- selected dialect keywords/functions;
- no automatic suggestions in comments/strings;
- incomplete/unparseable SQL fallback;
- identifiers requiring quoting;
- call-tip lookup.

Widget tests for:

- automatic popup after threshold;
- `Ctrl+Space` popup;
- insertion replaces only the typed prefix;
- catalog/schema updates refresh suggestions;
- completion type icons/labels;
- popup does not freeze while schema is loading.

#### Implementation

- Add `SqlCompletionService` and completion adapter.
- Seed keyword/function metadata.
- Resolve aliases and CTEs with SQLGlot where possible.
- Add lexical fallback.
- Add call tips.
- Debounce automatic completion.

#### Exit criteria

- All minimum completion cases in Section 12.3 pass.
- Completion is catalog-aware and materially better than static keyword completion.

#### Suggested commit

```text
feat(editor): add schema-aware SQL IntelliSense
```

### Phase 8 — Execution controller and DuckDB vertical slice

**Purpose:** complete the first end-to-end native workflow.

#### Red

Tests for:

- Idle/Running/Cancellation Requested/terminal state transitions;
- Run disabled during execution;
- stale request result ignored;
- immutable request snapshot;
- per-execution DuckDB connection lifecycle;
- preview truncation using limit-plus-one;
- structured query and import errors;
- request-specific cancellation;
- one query at a time.

Integration test:

1. add a temporary CSV through the catalog service;
2. enter SQL;
3. run through the Qt controller;
4. receive a result without blocking the test event loop;
5. verify row/column data and metrics.

#### Implementation

- Add `QueryController` and execution worker.
- Refactor DuckDB engine.
- Wire Run/Cancel toolbar actions and state.
- Wire result signal to a temporary result receiver; full result grid arrives next phase.
- Write history only after a terminal result, using the captured request.

#### Exit criteria

- A real DuckDB query runs end to end in the native app.
- The GUI stays responsive.
- Cancellation state is truthful.

#### Suggested commit

```text
feat(execution): run and cancel DuckDB queries in desktop worker
```

### Phase 9 — Result table selection, copy, sorting, and layout

**Purpose:** meet or exceed the useful `st.dataframe` interactions.

#### Red

Model tests for:

- row/column/header counts;
- display and raw-value roles;
- nulls;
- numeric/date/string sorting;
- defined null ordering;
- restoring original row order;
- filtered row mapping;
- no model mutation from worker thread.

Widget tests for:

- cell/range/row/column selection;
- `Ctrl+C` TSV copy;
- Copy with Column Names;
- visual column order reflected in copy;
- copy quoted header;
- insert header into editor;
- ascending/descending/clear sort cycle;
- preview-only sort indicator;
- column move, hide, show, auto-size, reset;
- preview search/filter;
- discontiguous selection serialization.

#### Implementation

- Add `PolarsTableModel`, `TypedSortProxyModel`, and `ResultTableView`.
- Add clipboard serializers.
- Add header and body context menus.
- Add local search/filter.
- Wire metrics/status.

#### Exit criteria

- The mandatory result-grid parity matrix is green.
- Sorting is type-aware and clearly preview-only.
- Clipboard output pastes correctly into a spreadsheet in manual tests.

#### Suggested commit

```text
feat(results): add selectable sortable result grid and clipboard actions
```

### Phase 10 — Schema, translation, messages, and full-query ordering

**Purpose:** complete analytical context around the preview.

#### Red

Tests for:

- schema task success/error display;
- schema column insertion and quoting;
- translated SQL panel;
- unsupported translation diagnostics;
- no statement loss;
- full-query ORDER BY wrapper generation;
- no automatic rerun on local header sort;
- message severity and detail display.

#### Implementation

- Complete schema worker/panel.
- Add translation and messages panels.
- Add Apply Ascending/Descending Order to Query action.
- Add result request details/metrics.

#### Exit criteria

- Schema, translation, and errors are available without leaving the main window.
- Full-query ordering is explicit and tested.

#### Suggested commit

```text
feat(desktop): add schema translation diagnostics and query ordering
```

### Phase 11 — History v2 and persistent preferences

**Purpose:** preserve prior workflows and desktop state.

#### Red

Tests for:

- v1-to-v2 history migration;
- UUID-based selection;
- malformed-record isolation;
- atomic write;
- record cap;
- restoring SQL only;
- restoring catalog with missing files;
- settings round trip;
- corrupt settings fallback;
- window/dock/splitter restore.

#### Implementation

- Upgrade `HistoryRepository`.
- Add History dock.
- Complete `SettingsService`.
- Add Reset Layout and Clear History.

#### Exit criteria

- Existing history is preserved.
- Restart restores normal desktop preferences.
- Duplicate display labels cannot select the wrong record.

#### Suggested commit

```text
feat(history): add versioned query history and desktop settings
```

### Phase 12 — Path-based export

**Purpose:** restore preview/full export without retaining complete output bytes in application state.

#### Red

Tests for:

- save-dialog cancellation;
- extension/filter normalization;
- overwrite confirmation;
- preview CSV/XLSX/Parquet;
- selection export respecting visual order;
- full DuckDB CSV/Parquet output;
- captured request/catalog used for export;
- source metadata change warning;
- temporary-file cleanup;
- cancellation;
- error leaves existing destination intact;
- XLSX size guard/streaming behavior.

#### Implementation

- Add export controller/service and format-specific writers.
- Wire native save dialog.
- Add progress/cancel UI.
- Replace DataFrame-to-byte full-export path.

#### Exit criteria

- Exported files reopen and match expected rows/columns/order.
- Full DuckDB CSV/Parquet export does not materialize the entire result as a Polars DataFrame plus bytes.
- Failed export does not corrupt the destination.

#### Suggested commit

```text
feat(export): write preview selection and full results to native paths
```

### Phase 13 — Optional Spark engine

**Purpose:** retain Spark without imposing it on the default desktop experience.

#### Red

Tests for:

- application import and launch without PySpark installed;
- engine selector reports Spark unavailable cleanly;
- Spark lazy import/session creation;
- request-specific job group;
- cancellation calls `cancelJobGroup`, not `cancelAllJobs`;
- JSON versus JSON Lines behavior;
- temporary view cleanup;
- Spark preview result conversion;
- Spark export temp-directory cleanup;
- actionable Java/Spark startup failure.

Run real Spark integration tests only in an environment with the optional extra and supported Java installed.

#### Implementation

- Move Spark dependency to optional extra.
- Add lazy session manager.
- Refactor engine lifecycle, views, cancellation, and export.
- Update UI availability messaging.

#### Exit criteria

- DuckDB-only installation has no Spark import/runtime requirement.
- Spark works when installed.
- Cancel targets only the current job group.

#### Suggested commit

```text
refactor(spark): make Spark optional lazy and request-scoped
```

### Phase 14 — Streamlit parity gate and removal

**Purpose:** make the native application the only supported UI.

#### Red / parity review

Run every acceptance criterion in Section 21. Add any missing regression tests before deleting old code.

#### Implementation

- Change `wherewolf` entry point to the desktop application.
- Add/finish `python -m wherewolf`.
- Delete:
  - `src/wherewolf/app.py`;
  - Streamlit-only `src/wherewolf/ui/` modules;
  - `.streamlit/`;
  - obsolete Streamlit engine cache factory;
  - Streamlit and `streamlit-ace` dependencies;
  - Streamlit AppTest tests;
  - Playwright dependency if no longer used.
- Remove temporary compatibility adapters.
- Search the repository for `streamlit`, `st.`, `streamlit_ace`, and obsolete session-state terminology.
- Replace placeholder or weak tests discovered during migration.

#### Exit criteria

- `wherewolf` launches a native Qt window.
- No Streamlit imports, dependencies, configuration, or supported code paths remain.
- Full tests and quality checks pass.

#### Suggested commit

```text
feat!: replace Streamlit with the native PyQt6 desktop application
```

### Phase 15 — CI, documentation, and release candidate

**Purpose:** validate distribution and make the cutover supportable.

#### Red / verification

- Build wheel and source distribution.
- Install wheel into a clean environment.
- Launch headless smoke test from installed wheel.
- Run cross-platform GUI smoke matrix.
- Run optional Spark job separately.
- Check package metadata and license contents.

#### Implementation

- Update CI as described in Section 22.
- Update README screenshots and usage.
- Document shortcuts, native dialogs, result-grid behavior, preview sorting, export, optional Spark installation, and GPL license.
- Add migration notes from 0.5.x.
- Update release workflow and changelog.
- Bump to `1.0.0` only after the release candidate passes.

#### Exit criteria

- Clean wheel installation works on supported platforms.
- Documentation matches actual UI.
- Manual acceptance matrix is signed off.
- Release artifact contains required license notices.

#### Suggested commits

```text
ci: test native desktop application across supported platforms

docs: document the Wherewolf 1.0 desktop workflow

chore: prepare 1.0.0 release
```

---

## 21. Acceptance criteria and parity matrix

Every item marked **Required** blocks Streamlit removal.

### 21.1 Launch and desktop behavior

- **Required:** `wherewolf` opens one native desktop window.
- **Required:** no browser tab or local web server is started.
- **Required:** `python -m wherewolf` opens the same application.
- **Required:** window geometry, docks, and splitter positions persist.
- **Required:** closing the main window shuts down workers cleanly or prompts when a cancellation cannot complete immediately.
- **Required:** normal DuckDB startup does not import/start Spark.

### 21.2 Dataset workflow

- **Required:** Add Datasets opens the operating system's native multi-file dialog where supported.
- **Required:** CSV, Parquet, JSON, JSON Lines, and XLSX filters are present.
- **Required:** `.xls` is not falsely advertised.
- **Required:** drag/drop adds supported local files.
- **Required:** duplicate resolved paths are not added twice.
- **Required:** aliases are editable and case-insensitively unique.
- **Required:** remove, copy alias/path, insert alias, and schema refresh work.
- **Required:** schema failures show the underlying error.

### 21.3 SQL editor

- **Required:** SQL syntax is highlighted.
- **Required:** line numbers, brace matching, undo/redo, find/replace, and toggle-comment work.
- **Required:** `Ctrl+Enter`/`Cmd+Enter` runs the selection or current statement.
- **Required:** multiple statements are not silently discarded.
- **Required:** `Ctrl+Space` shows completion.
- **Required:** automatic completion can be enabled/disabled.
- **Required:** `FROM`/`JOIN` suggests catalog aliases.
- **Required:** `alias.` suggests the correct schema columns.
- **Required:** dialect keywords/functions are suggested.
- **Required:** completion does not block while schema loads.
- **Required:** Format SQL exists on toolbar, menu, context menu, and shortcut.
- **Required:** formatting uses the source dialect and is one-step undoable.
- **Required:** formatting errors leave SQL unchanged and display a diagnostic.

### 21.4 Query lifecycle

- **Required:** one query can run at a time.
- **Required:** UI remains responsive during query execution.
- **Required:** Cancel reports “requested” until the worker terminates.
- **Required:** DuckDB cancel affects only the active request connection.
- **Required:** history/export use the captured execution request.
- **Required:** errors are structured and visible.
- **Required:** preview truncation is clearly indicated.

### 21.5 Results grid

- **Required:** individual cells are selectable.
- **Required:** rectangular ranges, rows, and columns are selectable.
- **Required:** `Ctrl+C`/`Cmd+C` copies selected values as spreadsheet-compatible TSV.
- **Required:** Copy with Column Names works.
- **Required:** column-name, quoted-column-name, and all-visible-column-name copy actions work.
- **Required:** column names can be inserted into the editor.
- **Required:** clicking a header sorts ascending, descending, then restores query order.
- **Required:** sorting is type-aware.
- **Required:** active local sort is labelled “Sorted preview only.”
- **Required:** columns can be moved, resized, auto-sized, hidden, shown, and reset.
- **Required:** clipboard serialization follows current visual row/column order.
- **Required:** preview search/filter can be cleared.
- **Required:** explicit Apply Order to Query action is separate from local sorting.

### 21.6 Supporting panels

- **Required:** Schema tab shows real schema or a real error.
- **Required:** Translation tab shows exact executable SQL.
- **Required:** Messages tab shows parse, translation, engine, and export errors.
- **Required:** execution time, preview row count, engine, and truncation are visible.

### 21.7 History and export

- **Required:** existing history file migrates without data loss in tested fixtures.
- **Required:** history entries use IDs, not display labels.
- **Required:** restoring missing files is explicit.
- **Required:** preview export works for CSV, XLSX, and Parquet.
- **Required:** selection export respects table visual order.
- **Required:** full DuckDB CSV/Parquet export writes directly to a file path.
- **Required:** export cancellation/error does not corrupt an existing destination.
- **Required:** a source-file change between preview and full export produces a warning.

### 21.8 Spark

- **Required for Spark extra:** Spark selector is available only when support is installed.
- **Required for Spark extra:** session starts lazily.
- **Required for Spark extra:** cancellation targets the request job group.
- **Required for Spark extra:** `.json` and `.jsonl` semantics are tested separately.
- **Required for Spark extra:** full export does not unconditionally call `toArrow()` for an unbounded result.

### 21.9 Removal and licensing

- **Required:** no Streamlit code or dependency remains.
- **Required:** package metadata and license files state `GPL-3.0-only`.
- **Required:** pre-cutover MIT terms are accurately preserved in notices.
- **Required:** About/Open-Source Licenses is present.
- **Required:** wheel and source distribution include license files.

---

## 22. Testing strategy

### 22.1 Test dependencies and environment

- Use `pytest` and `pytest-qt`.
- Use `qtbot` for widget lifecycle, events, focus, shortcuts, and signal waiting.
- Use `QSignalSpy` where it provides clearer signal assertions.
- Set `QT_QPA_PLATFORM=offscreen` or `minimal` in headless Linux CI.
- Inject fake file dialogs, clipboard adapters where appropriate, and engine factories.
- Do not automate actual native dialogs in CI.
- Do not use sleep-based synchronization when a signal or event-loop wait is available.

### 22.2 Unit tests

Organize new tests approximately as:

```text
tests/
├── domain/
│   └── test_models.py
├── services/
│   ├── test_catalog_service.py
│   ├── test_completion_service.py
│   ├── test_execution_service.py
│   ├── test_formatting_service.py
│   ├── test_statement_service.py
│   └── test_export_service.py
├── desktop/
│   ├── test_actions.py
│   ├── test_catalog_dock.py
│   ├── test_main_window.py
│   ├── test_result_table_view.py
│   ├── test_sql_editor.py
│   └── test_settings.py
├── execution/
│   ├── test_duckdb_engine.py
│   └── test_spark_engine.py
├── export/
│   ├── test_clipboard.py
│   └── test_exporters.py
├── storage/
│   └── test_history.py
└── integration/
    ├── test_desktop_duckdb_flow.py
    ├── test_desktop_export_flow.py
    └── test_desktop_spark_flow.py
```

### 22.3 High-value unit cases

#### Formatter

- comments before/after expressions;
- block comments;
- quoted semicolons;
- escaped quotes;
- quoted identifiers;
- multiple statements;
- trailing semicolon/no semicolon;
- DuckDB-specific syntax;
- Spark-specific syntax;
- invalid SQL;
- CRLF and LF.

#### Completion

- table context;
- alias-dot context;
- CTE context;
- nested query scope;
- ambiguous columns;
- unknown schema;
- string/comment suppression;
- quoted identifiers;
- case-insensitive prefix;
- manual empty-prefix request;
- call-tip signature.

#### Result model and clipboard

- nulls;
- integers versus lexical string order;
- decimals;
- dates/datetimes;
- booleans;
- multiline text;
- tabs and quotes;
- discontiguous selection;
- visual column move;
- sorted proxy mapping;
- hidden columns;
- headers included/excluded.

#### Execution

- immutable catalog snapshot;
- connection close on success/error/cancel;
- limit-plus-one truncation;
- stale signal suppression;
- cancellation state;
- no second concurrent run;
- engine unavailable error.

### 22.4 Integration tests

At minimum:

1. **CSV query flow** — add file, receive schema, complete alias/column, format query, execute, sort, copy with headers.
2. **Mixed file join** — CSV plus Parquet with DuckDB.
3. **Translation flow** — source dialect to engine SQL, no statement loss.
4. **History flow** — execute, restart repository objects, restore SQL/catalog.
5. **Preview export** — CSV/XLSX/Parquet reopen and compare.
6. **Full export** — direct DuckDB output, source snapshot warning, overwrite safety.
7. **Cancellation** — deterministic long-running DuckDB query or controlled fake engine.
8. **Spark flow** — optional CI job with Java and Spark extra.

### 22.5 Manual cross-platform acceptance

Automated tests cannot prove native-dialog appearance, file-manager drag/drop, platform clipboard integration, or all shortcut conventions. Before release, manually validate on:

- current supported Windows;
- current supported macOS;
- a supported Linux desktop environment.

Manual script:

1. install wheel into a clean environment;
2. launch `wherewolf`;
3. open multiple datasets through native dialog;
4. drag/drop another dataset;
5. verify aliases and schema;
6. use completion and Format SQL shortcut;
7. run a query and cancel a long query;
8. select/copy cells and headers into a spreadsheet;
9. sort and restore order;
10. move/hide/reset columns;
11. export preview and full result;
12. restart and verify layout/history;
13. inspect About and license notices;
14. repeat with Spark extra where available.

Record results in the release checklist.

### 22.6 Performance targets

Treat these as engineering targets measured on a representative development machine, not brittle CI thresholds:

- native main window first paint without Spark startup: approximately two seconds or better;
- completion popup from cached metadata: under 100 ms;
- sort a 1,000-row preview: visually immediate;
- copy a 1,000 x 20 preview selection: under 500 ms;
- UI remains responsive during schema load, query, and export.

Profile before optimizing. Do not trade correctness for an unmeasured micro-optimization.

---

## 23. CI and release workflow

### 23.1 CI jobs

Recommended workflow split:

1. **Core/unit job**
   - Ubuntu
   - Python 3.11 and 3.12
   - `QT_QPA_PLATFORM=offscreen`
   - lint, format check, type check, non-Spark tests

2. **Cross-platform Qt smoke job**
   - Ubuntu, Windows, macOS
   - one supported Python version, initially 3.12
   - install default dependencies
   - instantiate app/editor/main window
   - run selected widget/integration tests

3. **Spark integration job**
   - Ubuntu
   - supported Java version
   - install `[spark]`
   - run Spark-specific tests only

4. **Build job**
   - build wheel and sdist
   - inspect metadata/license
   - install wheel into clean environment
   - run installed-package smoke test

### 23.2 CI rules

- Use the repository's `./run.sh` where compatible with each runner; adapt its platform behavior deliberately for Windows if it is shell-specific.
- Do not start a real native file dialog.
- Do not start Spark in default jobs.
- Cache only through repository-approved `/tmp/wherewolf` paths on Linux; configure equivalent isolated paths on other platforms.
- Keep screenshots out of normal assertion paths unless a visual regression framework is deliberately introduced.

### 23.3 Release workflow

- Update package metadata before release.
- Ensure license files are included in wheel/sdist.
- Keep publishing permissions job-scoped.
- Pin reusable actions to reviewed immutable SHAs where repository policy permits.
- Publish release candidate first.
- Verify `uv tool install` and `wherewolf` launch from the published candidate in clean environments.

---

## 24. Migration and cutover strategy

### 24.1 Coexistence period

Until the native vertical slice is stable:

- keep `wherewolf` launching Streamlit;
- expose `wherewolf-desktop` for migration testing;
- share only UI-neutral services and domain models;
- do not duplicate fixes across two separate core implementations.

### 24.2 Cutover gate

Change the primary entry point only after:

- native DuckDB workflow is complete;
- editor formatting and completion are complete;
- result-grid parity is complete;
- history and export are complete;
- Spark optional behavior is validated or explicitly documented as unavailable in the release candidate;
- all acceptance criteria pass.

### 24.3 Removal

After cutover:

- delete the Streamlit app, custom browser, results renderer, CSS/config, and Streamlit tests;
- remove dependencies and lockfile entries;
- remove temporary compatibility adapters;
- remove Streamlit screenshots/instructions from docs;
- do not leave a hidden legacy launch flag.

### 24.4 User migration

- Preserve query history through v1-to-v2 migration.
- Start with system-default window settings when no Qt settings exist.
- Explain in release notes that the browser UI is replaced by a desktop window.
- Explain the license change and that prior releases retain prior MIT grants.
- Explain Spark's new optional installation command.

### 24.5 Rollback

Before release, tag the final Streamlit version. A rollback means releasing or directing users to that tagged version; it does not mean maintaining both code paths in the new branch indefinitely.

---

## 25. File-level change matrix

### 25.1 Add

- `src/wherewolf/__main__.py`
- `src/wherewolf/domain/*`
- `src/wherewolf/services/*`
- `src/wherewolf/desktop/*`
- `src/wherewolf/execution/base.py`
- `src/wherewolf/execution/registry.py`
- `src/wherewolf/execution/spark_session.py`
- file-oriented export modules
- Qt/widget/service tests
- history migration fixtures
- license notices
- desktop documentation and screenshots

### 25.2 Rewrite or materially modify

- `src/wherewolf/cli.py`
- `src/wherewolf/constants.py`
- `src/wherewolf/execution/models.py`
- `src/wherewolf/execution/duckdb_engine.py`
- `src/wherewolf/execution/spark_engine.py`
- `src/wherewolf/export/exporter.py` or replace it with focused modules
- `src/wherewolf/storage/history.py`
- `src/wherewolf/translation/translator.py`
- `pyproject.toml`
- `uv.lock`
- `README.md`
- `LICENSE`
- `.github/workflows/ci.yml`
- release workflow
- package/version tests

### 25.3 Delete at cutover

- `src/wherewolf/app.py`
- `src/wherewolf/engines.py` if fully superseded
- `src/wherewolf/ui/file_browser.py`
- `src/wherewolf/ui/results.py`
- obsolete `src/wherewolf/ui/__init__.py`
- `.streamlit/`
- Streamlit-specific tests
- Streamlit and `streamlit-ace` dependencies
- Playwright when no remaining tests require it

Before deleting a file, use repository search to prove every retained behavior has a replacement and every import is removed.

---

## 26. Pull-request and commit strategy

The migration is large enough to review in slices. Recommended pull requests:

### PR 1 — License, contracts, and desktop skeleton

Phases 0–3:

- rights audit and relicense;
- dependency compatibility;
- immutable contracts;
- engine registry;
- native shell and temporary entry point.

### PR 2 — Catalog and editor

Phases 4–7:

- native dialogs/drag-drop;
- catalog;
- QScintilla editor;
- formatter;
- IntelliSense.

### PR 3 — DuckDB execution and results

Phases 8–10:

- execution controller;
- per-request DuckDB lifecycle;
- result grid;
- schema, translation, diagnostics, ordering.

### PR 4 — History, export, Spark, and cutover

Phases 11–15:

- history/settings;
- export;
- optional Spark;
- Streamlit removal;
- CI/docs/release.

If one agent must execute continuously, retain these as internal review checkpoints and keep commits independently testable.

Recommended conventional-commit sequence is listed in each phase. Avoid mixing formatting-only repository churn with functional commits.

---

## 27. Risk register

| Risk | Impact | Mitigation |
|---|---|---|
| Relicensing authority is incomplete | Cannot legally distribute GPL-only PyQt/QScintilla application as planned | Make rights audit a hard Phase 0 gate; document contributor consent |
| QScintilla dynamic completion API is less flexible than expected | IntelliSense UX regresses | Prototype dynamic popup/type metadata first; isolate it behind adapter; use direct Scintilla messages where tested |
| SQLGlot cannot parse incomplete SQL | Completion or formatting fails | Completion has lexical fallback; formatting is non-destructive and reports diagnostics |
| SQLGlot changes comments during formatting | User SQL is damaged | Add comment fixtures; no mutation on parse/generation uncertainty; preserve one-step undo |
| Qt tests fail in headless CI | Unstable pipeline | Use `pytest-qt`, offscreen/minimal platform, injected dialogs, cross-platform smoke jobs |
| Platform Qt wheel/QScintilla compatibility | Installation failures | Resolve in Phase 0, test wheel install on Windows/macOS/Linux before cutover |
| Spark dominates startup/package size | Desktop still feels heavy | Optional extra, lazy import, lazy session, default DuckDB path |
| DuckDB cancellation from GUI thread is unsafe in chosen worker design | Cancel hangs or targets wrong work | Build cancellation spike; expose request-specific handle; test deterministic long query; do not rely on blocked queued slot |
| Result copying mishandles tabs/newlines/nulls | Spreadsheet paste corruption | Central serializer with fixtures and manual paste matrix |
| Local sorting is confused with full-result ordering | Incorrect analytical conclusions | Persistent preview-only indicator; separate explicit query-order action |
| Full export exhausts memory | Crash/data loss | File-oriented writers, limits for XLSX, temp paths, cancellation, no session byte blobs |
| History migration corrupts user data | Data loss | Fixture-based migration, backup before first v2 write, atomic replace |
| Dual UI period creates divergent behavior | Maintenance burden | Keep coexistence short; share services; hard cutover/removal gate |
| Excessive Qt styling recreates browser fragility | UI maintenance cost | System style, minimal QSS, native controls |

---

## 28. Definition of done

The work is complete when all of the following are true:

1. The repository protocol and TDD requirements were followed and recorded.
2. Rights to relicense were confirmed.
3. Package/license metadata is `GPL-3.0-only` and prior MIT releases are accurately noted.
4. `wherewolf` launches a native PyQt6 application.
5. No Streamlit runtime, browser server, or web editor remains.
6. Native file and save dialogs work.
7. Drag/drop and catalog management work.
8. QScintilla editor provides syntax highlighting, completion, call tips, selected/current-statement execution, and formatting.
9. Format SQL is available by button, menu, context menu, and configurable hotkey and is one-step undoable.
10. Catalog- and schema-aware `alias.` completion works.
11. DuckDB query execution is request-scoped and responsive.
12. Spark is optional, lazy, and request-cancellable when installed.
13. Result values, ranges, rows, and columns are selectable.
14. Result copying and column-name copying work in visual order.
15. Result preview sorting is type-aware and clearly labelled.
16. Columns can be reordered, resized, hidden, shown, and reset.
17. Full-query ordering is an explicit separate action.
18. Schema, translation, messages, metrics, history, settings, and export work.
19. Full exports are path-based and do not retain full byte payloads in UI state.
20. Existing history migrates through tested fixtures.
21. Unit, widget, integration, build, and supported cross-platform smoke tests pass.
22. The clean installed wheel launches successfully.
23. README, shortcuts, optional Spark instructions, migration notes, and license notices are accurate.
24. The final repository search finds no unintended Streamlit code or stale documentation.

---

## 29. Agent final handoff report

When implementation is complete, the executing agent must provide a final report containing:

- branch and commit list;
- pull requests or review checkpoints;
- exact files added, changed, and deleted;
- dependency and license changes;
- automated test counts and results;
- cross-platform manual acceptance results;
- performance observations;
- known limitations;
- any acceptance criterion not met, with explicit reason;
- release command/output or release-candidate artifact details;
- location of the session log and this plan.

Do not describe untested behavior as complete.

---

## 30. Reference material

Repository-specific:

- Wherewolf repository: <https://github.com/beallio/wherewolf>
- Repository agent protocol: <https://github.com/beallio/wherewolf/blob/main/AGENTS.md>
- Current package metadata: <https://github.com/beallio/wherewolf/blob/main/pyproject.toml>
- Current Streamlit application: <https://github.com/beallio/wherewolf/blob/main/src/wherewolf/app.py>
- Current DuckDB engine: <https://github.com/beallio/wherewolf/blob/main/src/wherewolf/execution/duckdb_engine.py>
- Current Spark engine: <https://github.com/beallio/wherewolf/blob/main/src/wherewolf/execution/spark_engine.py>
- Current translator: <https://github.com/beallio/wherewolf/blob/main/src/wherewolf/translation/translator.py>
- Current history storage: <https://github.com/beallio/wherewolf/blob/main/src/wherewolf/storage/history.py>

Framework and editor:

- PyQt: <https://riverbankcomputing.com/software/pyqt/intro>
- QScintilla introduction: <https://riverbankcomputing.com/software/qscintilla/intro>
- QScintilla documentation: <https://www.riverbankcomputing.com/static/Docs/QScintilla/>
- Qt `QFileDialog`: <https://doc.qt.io/qt-6/qfiledialog.html>
- Qt `QAbstractTableModel`: <https://doc.qt.io/qt-6/qabstracttablemodel.html>
- Qt `QSortFilterProxyModel`: <https://doc.qt.io/qt-6/qsortfilterproxymodel.html>
- Qt model/view architecture: <https://doc.qt.io/qt-6/model-view-programming.html>
- Qt `QSettings`: <https://doc.qt.io/qt-6/qsettings.html>
- Qt threading: <https://doc.qt.io/qt-6/qthread.html>

Core libraries:

- SQLGlot: <https://github.com/tobymao/sqlglot>
- DuckDB Python API: <https://duckdb.org/docs/stable/clients/python/overview>
- Spark Python API: <https://spark.apache.org/docs/latest/api/python/>

