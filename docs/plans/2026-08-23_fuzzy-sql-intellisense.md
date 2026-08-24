# Plan: Fuzzy SQL IntelliSense for Aliases and Functions (fuzzy-sql-intellisense)

## Context

### Problem Definition

Wherewolf already offers schema-aware SQL completion, but the useful candidates are
filtered twice as strict prefixes: `SqlCompletionService.complete()` uses `startswith()`
for catalog tables, CTEs, columns, functions, and keywords, then
`CompletionAdapter.request_completion()` sends them through Scintilla's prefix-oriented
`SCI_AUTOCSHOW`. Consequently, `FROM mon` finds `monthly_sales`, while `FROM sales` does
not; `DATE_` finds `DATE_TRUNC`, while `trunc` or `dt` does not.

The same audit found three related gaps that must be fixed in this round rather than
papered over by a matcher:

- catalog aliases and CTEs are candidates, and a previously typed table alias such as
  `o.` resolves its columns, but the alias `o` itself is not suggested;
- SELECT-expression aliases such as `revenue_total` are not offered later in the query;
- the adapter connects `userListActivated` but displays `SCI_AUTOCSHOW`, so its custom
  `insert_text` path is not used by real popup activation. On the checked-in code,
  lowercase `co` produces internal `COALESCE` candidates but QScintilla closes its
  case-sensitive popup; uppercase `CO` inserts `COALESCE` without the intended `(`;
- Spark completion follows a 28-entry curated tuple even when the optional Spark engine is
  installed, leaving hundreds of locally available Spark SQL functions undiscoverable.

The plan-author research used the repository's installed QScintilla 2.14.1 and DuckDB
1.5.5. A normal autocomplete list rejected `dt` against `DATE_TRUNC`; a pre-ranked
`SCI_USERLISTSHOW` emitted `userListActivated` and the existing replacement path inserted
`DATE_TRUNC(`. A pure ordered-subsequence scan over 790 identifier-shaped DuckDB
expression-function names averaged about 0.57 ms per scan. Scintilla documents that its
normal autocomplete selects entries character-by-character from the start and auto-hides
when no viable match exists, while user lists return a list identifier and selected text:
<https://www.scintilla.org/ScintillaDoc.html#Autocompletion>.

DuckDB exposes locally available scalar, aggregate, macro, table, and table-macro metadata
through `duckdb_functions()`:
<https://duckdb.org/docs/stable/sql/meta/duckdb_table_functions>. The installed version
returned 616 distinct scalar names, 88 aggregate names, 118 macro names, and 87 table
function names, compared with Wherewolf's 28 curated DuckDB entries. Loading all relevant
overload rows through one fresh in-memory connection took about 24 ms locally. Query this
metadata once and cache the normalized immutable result; never open a connection or query
metadata for each keystroke.

Spark 4.2.0 exposes installed SQL functions through `SparkSession.catalog.listFunctions()`
and separates system/user name discovery through `SHOW SYSTEM FUNCTIONS` and
`SHOW USER FUNCTIONS`:
<https://spark.apache.org/docs/4.2.0/api/python/reference/pyspark.sql/api/pyspark.sql.Catalog.listFunctions.html>
and <https://spark.apache.org/docs/latest/sql-ref-syntax-aux-show-functions.html>. A
plan-author validation against the lockfile version returned 574 system entries: 551 were
identifier-shaped, all 551 had non-empty usage descriptions, 537 began with a directly
insertable function-call signature, and 14 represented operator or special SQL syntax needing
filtering or curated overrides. `DESCRIBE FUNCTION` documents the same name/class/usage
metadata: <https://spark.apache.org/docs/latest/sql-ref-syntax-aux-describe-function.html>.

The validated local Spark JVM took about 3.9 seconds to start, and the first metadata listing
took about 1.2-2.2 seconds. Python API reflection is not an authoritative shortcut: it missed
50 valid SQL names and included 44 Python helpers that were not system SQL functions. A fresh
`newSession()` returned the 574 built-ins without inheriting a temporary UDF registered in the
root session. Therefore load the live Spark catalog once, off the GUI thread, from a clean child
session; keep the curated tuple usable while it loads and after any failure. Never load Spark at
application startup, on DuckDB-only use, or from the per-keystroke completion path.

### User-visible contract

Completion matching is deterministic and case-insensitive. "Fuzzy" means, in this order:

1. exact match;
2. prefix match;
3. token-initial match across underscores, hyphens, whitespace, and camel-case boundaries
   (`dt` -> `DATE_TRUNC`, `ci` -> `customer_identifier`);
4. contiguous substring match (`sales` -> `monthly_sales`, `trunc` -> `DATE_TRUNC`);
5. bounded ordered-subsequence match.

This round does not add edit-distance spelling correction or a new dependency. Reject a
subsequence whose span/gaps exceed a documented constant so a short query does not match
most of the catalog. Rank first by match quality, then by the existing semantic relevance
for the current SQL context, then by the normalized label. Return at most 100 candidates.
Forced completion with an empty prefix remains supported and uses semantic/alphabetical
ordering before applying that cap.

Apply the matcher to every candidate source: catalog aliases, CTEs, cached columns,
in-statement aliases, functions, and keywords. Preserve the existing rule that a qualified
context such as `o.` returns only columns for the resolved relation. Suppressed strings and
comments still return no candidates.

When the selected execution engine is Spark and Spark is available, show the curated Spark
functions immediately and start one background discovery per process. A completion request
must never wait for the JVM. Once discovery succeeds, subsequent completion requests use the
installed local Spark built-in catalog. Do not force-open or mutate an already-visible popup
when the worker finishes. A late Spark result may populate the cache after the user switches
back to DuckDB, but it must not change any editor's active dialect or visible completion list.
Show a transient status-bar message while Spark metadata loads and report either the loaded
candidate count or that curated fallback remains active.

### Alias scope contract

Use `StatementService.find_statement()` to isolate the statement containing the cursor.
Use SQLGlot for accurate scope/alias extraction when it parses, with a conservative lexical
fallback for incomplete SQL. Symbols from another statement or a nested scope must not leak
into the current scope.

- In expression contexts, suggest visible `FROM`/`JOIN` aliases as `CompletionKind.TABLE`
  with detail such as `alias for monthly_sales`. Do not suggest them as new source tables in
  `FROM`/`JOIN` contexts.
- Continue resolving `alias.<prefix>` to only the aliased table's cached columns.
- Suggest SELECT-expression aliases as `CompletionKind.COLUMN`, with `column alias` detail,
  in `ORDER BY`. For DuckDB completion, also honor DuckDB's documented visibility: a
  non-aggregate alias may appear in `WHERE` and `GROUP BY`, an aggregate alias in `HAVING`,
  and a window alias in `QUALIFY`. Never offer SELECT aliases in a JOIN `ON` clause. DuckDB's
  alias behavior is documented at <https://duckdb.org/docs/current/sql/dialect/friendly_sql>.
- Support both `expression AS alias` and DuckDB prefix aliases (`alias: expression`).
- Same-SELECT-list lateral alias completion is deferred; do not suggest an alias merely
  because it appears later than the cursor in the same SELECT list.

Do not add a new `CompletionKind`: relation aliases use `TABLE`, and expression aliases use
`COLUMN`. Deduplicate labels case-insensitively after ranking so the user-list selection text
maps to exactly one `CompletionItem`; the higher-ranked context-valid candidate wins.

### Function metadata contract

Keep `SqlFunctionInfo`, `get_dialect_functions()`, and `lookup_function_info()` compatible
with existing callers while adding a table-function accessor or an explicit function
category needed by the completion service.

- For DuckDB, read only identifier-shaped names from `duckdb_functions()`. Expression
  contexts use scalar, aggregate, and macro rows; table-reference contexts use table and
  table-macro rows. Exclude pragmas and operator-shaped names.
- Group overloads deterministically. Use the curated signature when one already exists;
  otherwise render a stable primary signature from parameter metadata and indicate the
  number of additional overloads without putting all overloads in the popup. Compact very
  wide signatures to a documented maximum display length rather than rendering dozens of
  optional table-function parameters.
- Cache the successful or fallback tuple so repeated completion and call-tip requests do
  not reconnect. If metadata inspection fails, retain the curated list rather than losing
  completion or surfacing an editor error.
- Never run `INSTALL`, `LOAD`, or external/remote network access while building metadata.
  PySpark's existing loopback Python/JVM transport is permitted. DuckDB metadata describes a
  fresh Wherewolf connection, not every optional extension function.
- For Spark, keep the current curated tuple as the immediate and failure fallback. When the
  optional engine is selected and available, one background worker obtains the installed local
  built-ins from `catalog.listFunctions()` on a clean child session. Filter to safe
  identifier-shaped SQL calls, exclude keyword/operator pseudo-functions such as `CASE`, and
  merge curated overrides so known signatures and special insertion behavior remain stable.
  Parse only a bounded primary signature from Spark's free-form usage description; a missing or
  changed description falls back to `NAME(...)` rather than failing the catalog.
- Discover public Spark table-valued function names from the installed
  `pyspark.sql.tvf.TableValuedFunction` surface and intersect them with the live system catalog.
  Treat known generator functions such as `EXPLODE` as valid in both expression and table
  contexts; table-only functions such as `RANGE` are not expression candidates. Do not infer
  categories from implementation-class-name substrings.
- Cache an immutable successful or curated-fallback Spark result for the process. The blocking
  loader is callable only by the background metadata worker; `get_dialect_functions()`,
  `lookup_function_info()`, completion requests, and call tips never start Spark or wait on it.
- The editor's completion dialect follows the selected DuckDB/Spark execution engine for every
  open and newly-created editor instead of being hardcoded to DuckDB.

`lookup_function_info()` must search both expression and table-function metadata so a
selected table function can show the same call-tip behavior as a scalar function.

Persistent user-created macros/UDFs are out of scope. Preview execution creates isolated
request sessions for both engines, so DuckDB definitions do not survive the next in-memory
connection and Spark temporary functions do not cross child sessions. Remote Spark Connect,
cluster catalogs, extension-provided functions requiring non-default session configuration,
and vendor-specific completion for Azure SQL, Oracle, and PostgreSQL are also out of scope;
changing the input-dialect selector must not pretend those catalogs are implemented.

### Architecture Overview

Keep matching and SQL-symbol discovery Qt-free under `src/wherewolf/services/`. A small
`completion_matching.py` owns match classification/scoring. A small
`completion_symbols.py` owns current-statement scope extraction and its lexical fallback.
`completion_service.py` composes those results with catalog/schema metadata;
`completion_adapter.py` is the only module that owns QScintilla list presentation and
activation. Extend `CursorContext` with a clause classification only if needed for the alias
visibility rules; do not put UI state in domain records.

Add a Qt-free `spark_function_metadata.py` that normalizes live `Function` records without
importing PySpark at module import. Move the shared lazy local-session builder into
`execution/spark_runtime.py`, protected so metadata discovery and query execution reuse one
root context and receive isolated child sessions. Neither the metadata worker nor an individual
request calls `SparkSession.stop()` on that shared root. `spark_engine.py` delegates only session
creation to this helper and preserves its request-local views, cancellation, and execution
behavior.

Add a narrow `SparkMetadataController` plus `SparkMetadataWorker` under the desktop layer.
`MainWindow` triggers it only after the available Spark engine is selected, owns its bounded
shutdown, and ignores stale UI effects after an engine switch. The worker publishes only an
immutable success/fallback result and status; it never owns editors or QScintilla objects.

SQLGlot attaches source offsets to identifiers in the installed version, but not to every
container node such as `Select`. Use identifier spans plus AST ancestry and conservative
lexical boundaries to find the cursor's scope; do not assume every SQLGlot expression has
`start`/`end` metadata.

#### Core Data Structures

Keep `CompletionItem` unchanged. Add only service-local immutable records for match quality,
statement/table aliases, expression aliases, alias category (non-aggregate, aggregate, or
window), normalized function category/overload summary, and Spark catalog load state. Function
context is a set because a generator may be valid in both expression and table-reference
positions. These records carry no Qt types, open connections, mutable lists, or catalog
ownership.

#### Public Interfaces

Public behavior remains `SqlCompletionService.complete(context)` and `call_tip(context)`.
Add `SqlEditor.set_completion_dialect(dialect)` (default `duckdb`) so `MainWindow` can keep
all editor tabs synchronized with the execution-engine selector. Keep `CompletionItem`'s
existing shape and encode the deterministic match/semantic rank in its `sort_key` rather
than widening unrelated domain APIs. Keep `get_dialect_functions()` synchronous and
non-blocking; add one explicit blocking `load_spark_function_metadata()` entry point for the
worker and a read-only load-state/result accessor for the controller and tests.

#### Dependency Requirements

No dependency change is expected: use the existing DuckDB, SQLGlot, PyQt6, QScintilla, and
optional PySpark dependencies. The default installation must remain free of PySpark imports,
Spark startup, and Java requirements. Do not edit `pyproject.toml` or `uv.lock` unless verified
installed APIs prove the plan impossible, in which case stop and record the blocker instead of
choosing another fuzzy package.

#### Testing Strategy

Use bottom-up TDD: pure matcher tests, scope/symbol tests, DuckDB metadata tests, pure Spark
normalization/cache tests with fakes, one opt-in live Spark catalog test, service composition
tests, real offscreen QScintilla keyboard activation, then asynchronous MainWindow engine/tab
synchronization. Preserve the no-PySpark import boundary for default installs. Add
disposable-worktree mutations for six load-bearing behaviors before trusting the final full-suite
negative control. Manual popup appearance and cross-platform behavior remain explicit deferred
checks.

Relevant production files are:

- `src/wherewolf/services/completion_matching.py` (new);
- `src/wherewolf/services/completion_symbols.py` (new);
- `src/wherewolf/services/completion_context.py`;
- `src/wherewolf/services/completion_service.py`;
- `src/wherewolf/services/sql_metadata.py`;
- `src/wherewolf/services/spark_function_metadata.py` (new);
- `src/wherewolf/execution/spark_runtime.py` (new);
- `src/wherewolf/execution/spark_engine.py`;
- `src/wherewolf/desktop/spark_metadata_controller.py` (new);
- `src/wherewolf/desktop/workers/spark_metadata_worker.py` (new);
- `src/wherewolf/desktop/widgets/completion_adapter.py`;
- `src/wherewolf/desktop/widgets/sql_editor.py`;
- `src/wherewolf/desktop/main_window.py`.

The plan-author baseline on `main` was 825 passing tests with 7 Spark tests deselected;
the existing focused completion/context/adapter/editor suite passed 69 tests. Re-establish
and record the baseline after branching from the generated `dev` base rather than treating
these counts as a substitute for a fresh run.

**Slug used throughout this plan:** `fuzzy-sql-intellisense`

---

## Orchestration Contract

**Slug:** `fuzzy-sql-intellisense`

**Plan file:**

```text
docs/plans/2026-08-23_fuzzy-sql-intellisense.md
```

**Implementation branch:**

```text
feat/fuzzy-sql-intellisense
```

**Round-complete marker:**

```text
/tmp/wherewolf/fuzzy-sql-intellisense_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/fuzzy-sql-intellisense_finalized
```

**Review notes:**

```text
docs/review/fuzzy-sql-intellisense-review-*.md
```

Each review note ends with exactly one status trailer:

```text
STATUS: CHANGES_REQUESTED
```

or:

```text
STATUS: APPROVED
```

---

## Required Agent Protocol

1. Use the **implementer** skill.
2. Work from the repository root.
3. Branch from `dev`.
4. Commit this plan as the first commit on the implementation branch.
5. Follow TDD where behavior changes are testable.
6. Run quality gates before marking any round complete.
7. Do not write your own review.
8. Do not create files under `docs/review/`.
9. Do not delete files under `docs/review/`.
10. Review notes are durable audit records and must be committed.
11. Resolving a review note means:
    - implement the requested changes;
    - run quality gates;
    - commit the code/docs changes;
    - commit the review note itself if it is not already committed;
    - recreate the round-complete marker.
12. After finalization, stop polling and exit cleanly.

---

## Scope discipline

- Implement only the units the plan lists. Do not modify files outside the plan's scope.
- Do not change runtime behavior beyond what the plan specifies. A `refactor` or
  `cleanup` commit must preserve observable behavior.
- Never edit a test's expected value to make a behavior change pass. If a test
  legitimately must change, that change must be required by the plan or a review
  note, and you must record the rationale in the session log.
- If you spot an unrelated improvement, do not make it here — note it in the
  session log for a separate plan.

---

## Setup

Start from `dev`:

```bash
git checkout dev
git pull --ff-only origin dev
git checkout -b feat/fuzzy-sql-intellisense
```

Commit this plan first:

```bash
git add docs/plans/2026-08-23_fuzzy-sql-intellisense.md
git commit -m "docs(plan): add fuzzy-sql-intellisense implementation plan"
```

---

## Implementation Tasks

Follow strict Red-Green-Refactor. For every production behavior below, add the failing test
first, run the named focused test through `./run.sh`, record the expected assertion failure
in the session log, then implement the minimum behavior and rerun the focused tests. Commit
each numbered task once its tests pass; do not batch unrelated tasks.

### Task 1 - Record the baseline and create the durable session record

Emit the `AGENT_PROTOCOL_HANDSHAKE` from `AGENTS.md`. Run:

```bash
./run.sh uv sync
./run.sh uv run pytest -q
```

Record the exact commit, pass/fail/deselection totals, duration, and coverage total in
`docs/agent_conversations/2026-08-23_fuzzy-sql-intellisense.json`. Create valid JSON with
the required keys `date`, `task_objective`, `files_modified`, `tests_added`,
`design_decisions`, and `results`; add `deferred_and_unverified` before closeout. If the
baseline is not green, stop and diagnose it before writing implementation code.

Commit: `docs(intellisense): record fuzzy completion baseline`.

### Task 2 - Add the pure fuzzy matching kernel

**Red:** create `tests/test_completion_matching.py`. Assert exact, prefix, token-initial,
substring, and bounded ordered-subsequence classifications and their strict priority.
Cover case-insensitivity, underscore/camel-case tokenization, a non-match, an over-wide
subsequence rejected by the gap/span bound, deterministic ties, and empty-prefix behavior.
The tests must prove `dt -> DATE_TRUNC`, `ci -> customer_identifier`,
`sales -> monthly_sales`, and `trunc -> DATE_TRUNC` without making a typo/transposition an
implicit contract.

Run the new file and capture the import/behavior failure before implementation.

**Green:** add `src/wherewolf/services/completion_matching.py` with immutable/internal
match-quality data and one pure function returning a comparable score or `None`. Document
the subsequence bound as a named constant. Do not import Qt, DuckDB, SQLGlot, or a fuzzy
matching package. Refactor only after every Red case passes.

Commit: `feat(intellisense): add deterministic fuzzy matching`.

### Task 3 - Extract current-scope table and expression aliases

**Red:** extend `tests/test_completion_context.py` for reliable `SELECT`, `WHERE`,
`GROUP BY`, `HAVING`, `QUALIFY`, `ORDER BY`, and JOIN `ON` clause classification. Create
`tests/test_completion_symbols.py` for the symbol collector. Cover:

- `FROM monthly_sales AS o` and omitted-`AS` aliases;
- aliases that remain discoverable when the cursor is in the SELECT list before `FROM`;
- a broken/incomplete statement exercising the lexical fallback;
- SELECT aliases written as postfix `AS` and DuckDB prefix aliases;
- aggregate, non-aggregate, and window-expression classification;
- aliases from another semicolon-delimited statement and a nested subquery not leaking;
- same-SELECT aliases after the cursor not being reported as lateral candidates.

Run both focused files and record the missing clause/symbol behavior.

**Green:** add `src/wherewolf/services/completion_symbols.py` and minimally extend
`completion_context.py`. Isolate the current statement with `StatementService`, select the
innermost SQLGlot scope containing the cursor where possible, and retain a conservative
lexical fallback for unfinished SQL. Return immutable tuples in source order and do not
perform catalog/schema I/O.

Commit: `feat(intellisense): discover in-scope SQL aliases`.

### Task 4 - Load and cache DuckDB function metadata

**Red:** extend `tests/test_sql_metadata.py`. Against the installed DuckDB dependency,
assert that a non-curated expression function such as `SQRT` and table function such as
`READ_CSV` are available in their correct categories; operator/pragmas are absent; overload
normalization is stable; signatures are non-empty and bounded even for wide table functions;
null/empty parameter metadata is safe; lookup stays case-insensitive across expression and
table categories; and the curated signature wins for a known function. With monkeypatching,
prove two successive requests use one metadata load and prove a metadata-query exception
returns the curated fallback without raising. Keep the Spark curated-set assertions.

Run the new nodes and record their failure against the 28-entry static implementation.

**Green:** extend `src/wherewolf/services/sql_metadata.py` as specified in the Context.
Use a short-lived `duckdb.connect(database=":memory:")` only inside the cached loader, close
it deterministically, group rows without depending on database row order, and never
`INSTALL` or `LOAD`. Preserve the existing public call shapes; add the smallest explicit
accessor/category surface required for table functions. Expose no mutable cached collection.

Commit: `feat(intellisense): load DuckDB function metadata`.

### Task 5 - Discover and cache the installed Spark built-in catalog

**Red:** create `tests/test_spark_function_metadata.py` without requiring PySpark in the
default test tier. Feed immutable fake `Function` records and fake table-valued API names into
the normalizer. Assert identifier filtering, deterministic case-insensitive deduplication,
curated-signature precedence, bounded fallback signatures, keyword/operator pseudo-function
exclusion (`CASE` must not become a function insertion), expression-only/table-only/dual-context
classification, and immutable results. With fake session factories, prove:

- the blocking loader uses one clean child session and performs one catalog listing;
- a temporary root-session UDF is not merged into the built-in result;
- two callers receive the same cached tuple without another session or query;
- missing PySpark, missing descriptions, startup errors, and catalog errors return the curated
  Spark fallback without raising;
- importing `wherewolf.services`, `sql_metadata`, and completion modules does not import
  `pyspark` or start Java.

Add an opt-in `@pytest.mark.spark` integration test against the lockfile Spark version. It must
assert more than 500 identifier-shaped built-ins, a non-curated function such as `URL_DECODE`,
table-valued `RANGE`, dual-context `EXPLODE`, non-empty bounded signatures, and exclusion of
operator-shaped/special-syntax candidates. Add a second opt-in node that starts metadata loading
and a trivial `SparkEngine` query from separate Python threads, proves both receive isolated child
sessions on one root context, and proves completion metadata survives request cleanup. Run the
fake/default tests first and record their missing-module/API failures, then sync the Spark extra
and run the live nodes to record the static 28-entry/session-lifecycle failures. Restore the
default `./run.sh uv sync --locked` environment afterward.

**Green:** add `src/wherewolf/services/spark_function_metadata.py` and
`src/wherewolf/execution/spark_runtime.py`, then minimally adapt `sql_metadata.py` and
`spark_engine.py`. Keep PySpark imports inside the blocking runtime/loader functions. Protect root
session creation with a process-local lock, return `newSession()` children, and do not stop the
shared root from metadata or request cleanup. Normalize only metadata already returned by the
local catalog; do not execute user SQL, inspect datasets, contact a remote catalog, or probe every
function by executing it. The synchronous public lookup path returns the curated tuple until an
atomic immutable live result is ready.

Commit: `feat(intellisense): discover Spark built-in functions`.

### Task 6 - Compose fuzzy, alias-aware, context-correct completion

**Red:** extend `tests/test_completion_service.py` before changing the service. Use exact
label/kind/detail/order assertions for:

- catalog substring matching (`FROM sales` -> `monthly_sales`);
- token-initial function matching (`SELECT dt` -> `DATE_TRUNC`);
- substring function matching (`SELECT trunc` -> `DATE_TRUNC`);
- fuzzy qualified-column matching without columns from another relation;
- a visible table alias offered in SELECT/WHERE but not as a new FROM/JOIN source;
- `ORDER BY rev` offering `revenue_total`;
- DuckDB non-aggregate aliases in WHERE/GROUP BY, aggregate aliases in HAVING, and window
  aliases in QUALIFY, with JOIN `ON` as the negative case;
- DuckDB and Spark table functions in table-reference context, expression functions outside
  it, and a dual-context Spark generator such as `EXPLODE` in both valid positions;
- the curated Spark fallback before loading and a cached non-curated Spark function after a
  fake successful load, without the service starting Spark itself;
- exact/prefix matches preceding token/substring/subsequence matches, then semantic and
  alphabetical tie-breaking;
- case-insensitive duplicate labels collapsing to one context-preferred item;
- the 100-item cap, empty-prefix forced ordering, broken-SQL fallback, and existing
  string/comment suppression.

Add dynamic DuckDB and Spark function call-tip cases so live metadata is useful beyond the
popup. Run the focused service suite and record the expected failures.

**Green:** refactor `src/wherewolf/services/completion_service.py` to gather context-valid
candidates first, apply `completion_matching` uniformly, merge `completion_symbols`,
deduplicate after ranking, and cap last. Reuse current identifier quoting and cached schema
only. Preserve CTE shadowing and `schema is None` non-blocking behavior. Do not query DuckDB
or inspect files directly from this service.

Commit: `feat(intellisense): complete fuzzy aliases and functions`.

### Task 7 - Make the QScintilla user-list path real

**Red:** extend `tests/test_completion_adapter.py` and `tests/test_sql_editor.py`. Do not
limit this task to mocked `SendScintilla` calls: show an offscreen registered widget, drive
it with `QTest`, and assert the actual editor text after activation. Cover:

- the adapter sends `SCI_USERLISTSHOW` with `COMPLETION_LIST_ID`, not `SCI_AUTOCSHOW`;
- lowercase `co` keeps an uppercase `COALESCE` result list active;
- selecting fuzzy `dt -> DATE_TRUNC` with Enter replaces only `dt` and produces exactly
  `DATE_TRUNC(`;
- selecting `sales -> monthly_sales` replaces only the typed token;
- function selection displays its call tip/signature;
- an empty/stale result cancels an already-open list and clears active item state;
- wrong list IDs are ignored;
- multiword keywords and labels containing spaces or `?` remain one selectable item by
  configuring explicit list/type separators that cannot collide with normal SQL labels;
- typing another character while a user list is open updates the typed text and refreshes
  the application-ranked list instead of selecting or cancelling a stale entry;
- replacement is one undo unit and does not re-open completion recursively from the
  resulting `textChanged` signal.

First run the focused nodes and record the current lowercase-popup, missing-parenthesis,
and signal-path failures.

**Green:** change only presentation/insertion behavior in
`src/wherewolf/desktop/widgets/completion_adapter.py` and the narrow re-entrancy hook needed
in `sql_editor.py`. Use Scintilla's user-list selection signal already connected by the
adapter. Keep visual type IDs and service-owned ranking. Cancel stale lists explicitly and
show the selected function's already-computed detail as a call tip without issuing another
completion request. Configure Scintilla's list and type separators explicitly; do not join
items with spaces because existing keywords such as `GROUP BY` are single candidates.

Commit: `fix(intellisense): activate fuzzy QScintilla selections`.

### Task 8 - Follow the selected execution engine and load Spark metadata asynchronously

**Red:** extend `tests/test_sql_editor.py` and `tests/test_main_window.py`, and create
`tests/test_spark_metadata_controller.py` with a fake slow/failing loader so the default tier
does not start Spark. Make the completion spy capture full contexts and assert:

- a standalone editor defaults to `duckdb` and validates `set_completion_dialect()`;
- selecting Spark changes subsequent completion contexts to `spark` for every existing tab;
- a tab created after the switch starts with Spark completion metadata;
- switching back restores DuckDB completion;
- Spark selection returns promptly, shows curated `EXPLODE` immediately, starts exactly one
  background metadata load across all tabs, and leaves the GUI event loop responsive;
- a successful load makes a fake non-curated Spark function available on the next request
  without force-opening or mutating an active popup;
- a loader failure leaves curated Spark completion active, records one non-blocking status, and
  does not retry on every selection, tab, or keystroke;
- switching back to DuckDB before a delayed result arrives lets the cache finish but does not
  change editor dialects, visible popups, or status to claim Spark is active;
- query execution and metadata loading share isolated child sessions without either worker
  stopping the root context;
- closing the window while the metadata worker is active uses a bounded shutdown and does not
  deliver signals to deleted editors;
- a real request after the Spark switch excludes a DuckDB-only table function, and switching
  back reverses that metadata source;
- changing only the vendor input-dialect selector does not claim unsupported vendor
  function metadata;
- disabled/unavailable Spark remains unselectable through the normal UI path.

Run the nodes and record that `SqlEditor.request_completion()` currently hardcodes
`duckdb`.

**Green:** add `SqlEditor.set_completion_dialect(dialect)` and replace the hardcoded value.
Connect `MainWindow.engine_selector` to a small synchronization method that updates all entries
in `_editor_states`; initialize each new editor from the current engine. Add
`SparkMetadataController` and `SparkMetadataWorker`, trigger the controller only when the
available Spark engine is selected, and keep all blocking PySpark work in the worker. Publish
transient loading/success/fallback status through `MainWindow`; do not refresh an open user list
from the completion callback. Use existing `EngineKind` values and keep metadata discovery
separate from query submission even though both reuse the shared local Spark runtime.

Commit: `fix(intellisense): load selected engine metadata asynchronously`.

### Task 9 - Document the behavior and close the session record

Update `README.md` where it describes Ctrl+Space and completion so users know that matching
can find the middle/token initials of catalog names, aliases, columns, and functions. Add
`docs/specs/sql-completion.md` containing the matching order, alias visibility, function
metadata/fallback rules, candidate cap, and explicit non-goals from this plan. Add a concise
`CHANGELOG.md` Unreleased entry. Do not change README image cache busters because this task
does not create a release tag.

Document that Spark completion initially uses a curated fallback, then discovers the installed
local built-in catalog in the background; define “comprehensive” as built-ins from the isolated
local Wherewolf Spark runtime, not remote catalogs or persistent UDFs. Document that selecting
Spark can start the bounded local JVM even before the first query, while DuckDB-only startup
remains free of PySpark imports and Java requirements.

Finish the session JSON with every modified file, every added test node, Red and Green
outputs, design decisions, final gate tallies, mutation results, and the deferred items from
Verification. Validate the JSON through the wrapper or a read-only standard-library parser.

Commit: `docs(intellisense): document fuzzy SQL completion`.

---

## Quality Gates

Run before marking any round complete:

```bash
scripts/orchestration/run-quality-gates
scripts/orchestration/check-review-notes-not-deleted
git status --short
```

The round is not complete unless:

1. all requested implementation work is done;
2. all relevant tests pass;
3. build/typecheck gates pass;
4. review notes have not been deleted;
5. the working tree is clean;
6. all code/docs changes are committed.

---

## Verification

Apply `references/verification-standards.md` from the orchestration-plan-author skill.
Every check below can fail, failure output is explicit, the mutation checks run before the
final negative control, and command pipelines enable `pipefail`.

### V1 - Focused behavior and full quality gates

```bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

./run.sh uv run pytest -q --no-cov \
  tests/test_completion_matching.py \
  tests/test_completion_symbols.py \
  tests/test_completion_context.py \
  tests/test_sql_metadata.py \
  tests/test_spark_function_metadata.py \
  tests/test_completion_service.py \
  tests/test_completion_adapter.py \
  tests/test_sql_editor.py \
  tests/test_spark_metadata_controller.py \
  tests/test_main_window.py

scripts/orchestration/run-quality-gates
```

Both commands must exit 0. Failure is any failed/skipped focused behavior, collection error,
Ruff/format/type failure, or full-suite failure. Record the focused and full-suite tallies;
do not infer success from the last line of a pipeline.

### V2 - Direct service acceptance cases

Run a standalone assertion script through the real service. Use a catalog fixture named
`monthly_sales` with `customer_identifier` and `gross_revenue` columns and the exact SQL
cases below:

```bash
./run.sh uv run python - <<'PY'
from pathlib import Path
from uuid import uuid4

from wherewolf.domain.enums import CompletionKind, SourceFormat
from wherewolf.domain.models import CatalogEntry, ColumnSchema, CompletionContext
from wherewolf.services.completion_service import SqlCompletionService

catalog = (
    CatalogEntry(
        id=uuid4(),
        alias="monthly_sales",
        path=Path("/tmp/monthly_sales.csv"),
        source_format=SourceFormat.CSV,
        schema=(
            ColumnSchema("customer_identifier", "VARCHAR"),
            ColumnSchema("gross_revenue", "DOUBLE"),
        ),
    ),
)
service = SqlCompletionService()

def labels(sql: str, cursor: int | None = None):
    cursor = len(sql) if cursor is None else cursor
    return {
        (item.label, item.kind)
        for item in service.complete(CompletionContext(sql, cursor, "duckdb", catalog))
    }

assert ("monthly_sales", CompletionKind.TABLE) in labels("SELECT * FROM sales")
assert ("DATE_TRUNC", CompletionKind.FUNCTION) in labels("SELECT dt")
qualified = labels("SELECT o.rev FROM monthly_sales AS o", len("SELECT o.rev"))
assert ("gross_revenue", CompletionKind.COLUMN) in qualified
assert ("customer_identifier", CompletionKind.COLUMN) not in qualified
assert ("o", CompletionKind.TABLE) in labels(
    "SELECT o FROM monthly_sales AS o", len("SELECT o")
)
assert ("revenue_total", CompletionKind.COLUMN) in labels(
    "SELECT gross_revenue AS revenue_total FROM monthly_sales ORDER BY rev"
)
assert ("SQRT", CompletionKind.FUNCTION) in labels("SELECT sqr")
assert ("READ_CSV", CompletionKind.FUNCTION) in labels("SELECT * FROM read_c")
print("PASS: fuzzy catalog, alias, column, expression-function, and table-function cases")
PY
```

The command must exit 0 and print the PASS line. Any missing/wrong-kind candidate or
qualified-column leak fails an assertion. Table functions remain
`CompletionKind.FUNCTION`, as required by the Context; do not weaken this assertion.

### V3 - Real QScintilla activation path

Run the exact keyboard-driven adapter/editor tests added in Task 7 with Qt's offscreen
platform (already configured by `tests/conftest.py`):

```bash
./run.sh uv run pytest -q --no-cov tests/test_completion_adapter.py tests/test_sql_editor.py -k \
  'user_list or lowercase or fuzzy or function_insertion or stale_list or separator or refresh or completion_dialect'
```

Failure is zero collected tests, any failed test, `dt` remaining in the buffer, a missing or
duplicate opening parenthesis, no call tip, or an active stale popup. Record collected and
passed counts.

### V4 - Default-tier function-catalog isolation and fallback

Run the DuckDB loader and fake Spark normalization/cache tests separately so a broad completion
success cannot hide a loader defect and the default environment cannot import PySpark:

```bash
./run.sh uv run pytest -q --no-cov \
  tests/test_sql_metadata.py \
  tests/test_spark_function_metadata.py \
  tests/test_import_boundaries.py -v
```

Failure is a missing dynamic `SQRT`/`READ_CSV`, an operator/pragma leaking in, a second
DuckDB connection, Spark fake metadata losing a safe dynamic name, a special-syntax Spark
candidate leaking in, an empty signature, a second Spark load, PySpark appearing in the default
import graph, or a raised exception rather than the curated fallback.

### V5 - Live installed Spark catalog

Run this opt-in tier after the default-tier tests. Restore the default temporary environment even
when pytest fails so the final negative control proves DuckDB-only behavior:

```bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

./run.sh uv sync --extra spark --locked
set +e
./run.sh uv run pytest -q --no-cov -m spark \
  tests/test_spark_function_metadata.py -v
spark_test_status=$?
set -e
./run.sh uv sync --locked

if [ "$spark_test_status" -ne 0 ]; then
  printf 'FAIL: live Spark metadata test exited %s\n' "$spark_test_status" >&2
  exit "$spark_test_status"
fi
printf 'PASS: live installed Spark metadata catalog\n'
```

The command must collect and pass the live node rather than skip it. Failure is fewer than 500
safe built-ins, missing `URL_DECODE`, `RANGE`, or `EXPLODE`, an invalid `CASE` function insertion
or operator-shaped label, an empty/overlong signature, a temporary root-session UDF leaking into
the child catalog, a second catalog load, metadata/query threads receiving the same child session
or stopping the shared root, a non-zero pytest status, or failure to restore the default locked
environment. Record the Spark and Java versions, discovered/accepted/filter counts, loader
duration as an observation rather than a timing assertion, and the exact test tally.

### V6 - Mutation checks in disposable worktrees

Commit the implementation first. For each mutation, create a fresh detached worktree below
an explicit `mktemp -d /tmp/wherewolf/fuzzy-sql-intellisense-mutation.XXXXXX` parent, apply
only the named mutation there, confirm `git diff --quiet` returns non-zero (the mutation
really changed production), and run the listed focused test. A collection error, missing
test, command-not-found error, or failure unrelated to the named assertion is inconclusive.

Use this setup from the primary checkout for each mutation:

```bash
mutation_parent=$(mktemp -d /tmp/wherewolf/fuzzy-sql-intellisense-mutation.XXXXXX)
mutation_tree="$mutation_parent/worktree"
git worktree add --detach "$mutation_tree" HEAD
cd "$mutation_tree"
```

1. Make the matcher accept prefixes only. The `sales`, `trunc`, and `dt` matching tests must
   fail.
2. Make symbol collection return no SELECT aliases. The `ORDER BY revenue_total` service
   test must fail while catalog completion still passes.
3. Replace `SCI_USERLISTSHOW` with `SCI_AUTOCSHOW`. The lowercase/fuzzy Enter activation test
   must fail.
4. Make DuckDB metadata return only the old curated tuple. The dynamic `SQRT` and `READ_CSV`
   metadata test must fail.
5. Make Spark normalization return only the curated tuple. The fake live-catalog test for a
   non-curated Spark function must fail without importing or starting PySpark.
6. Hardcode `CompletionContext.dialect` back to `duckdb`. The existing-tab and new-tab Spark
   synchronization tests must fail.

Record the exact failing node IDs. Remove each disposable worktree with
`git restore --source=HEAD -- <exact-mutated-production-file>`, return to the primary
checkout, and run `git worktree remove "$mutation_tree"` before creating the next one. Do
not restore or reset the primary implementation checkout.

### V7 - Final negative control

Run only after V6 and from the primary implementation checkout:

```bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

scripts/orchestration/check-review-notes-not-deleted
./run.sh uv sync --locked
./run.sh uv run ruff check .
./run.sh uv run ruff format --check .
./run.sh uv run ty check src/
./run.sh uv run pytest -q

status=$(git status --porcelain)
if [ -n "$status" ]; then
  printf 'FAIL: worktree is not clean:\n%s\n' "$status" >&2
  exit 1
fi
printf 'PASS: review notes preserved, gates green, primary worktree clean\n'
```

Every command must exit 0, the full default suite must exceed the freshly recorded Task 1 baseline
because new tests were added, and the final status must be empty. V5 proves that the final
Spark path works against the installed runtime; V6 proves that the final green result depends on
the new behavior rather than an empty implementation.

### Manual acceptance and deferred verification

Before marking the round complete, manually run `./run.sh uv run wherewolf` on the local
desktop when a display is available and record the result in the session log:

1. Add a disposable dataset whose alias is `monthly_sales` and whose schema includes
   `customer_identifier` and `gross_revenue`.
2. Type `FROM sales`, `SELECT dt`, `SELECT o.rev ... AS o`, and an `ORDER BY rev` query;
   verify the expected item is visible, can be selected with keyboard and mouse, replaces
   only the typed text, and function selection shows a call tip.
3. With the optional Spark extra installed, switch the execution engine to Spark. Verify the UI
   remains responsive, curated `EXPLODE` is immediately available, loading status appears once,
   and a non-curated built-in such as `URL_DECODE` becomes fuzzy-searchable after the success
   status. Verify table-context `RANGE`, switch back before and after loading, and confirm
   DuckDB-only dynamic functions and dialect state reverse correctly without a stale popup.

If a real display or Spark installation is unavailable, do not fabricate success. Record
those steps as deferred. The following remain explicitly unverified unless separately
performed and documented:

- popup placement, colors, truncation, and accessibility on macOS and Windows;
- real optional-extension functions beyond a fresh DuckDB connection;
- persistent user-created DuckDB macros/UDFs and Spark temporary functions/UDFs;
- remote Spark Connect, cluster catalogs, and non-default Spark extension functions;
- PySpark versions other than the lockfile version unless an additional compatibility run is
  explicitly recorded; runtime parsing remains defensive and falls back to curated metadata;
- Azure SQL, Oracle, and PostgreSQL-specific function catalogs;
- completion behavior for deeply correlated/nested SQL scopes beyond the automated cases;
- sustained latency with unusually large schemas/catalogs (record the local matcher and
  metadata-load measurements, but do not turn wall-clock timing into a flaky CI assertion).

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished fuzzy-sql-intellisense
```

This writes:

```text
/tmp/wherewolf/fuzzy-sql-intellisense_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer fuzzy-sql-intellisense`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/fuzzy-sql-intellisense-review-*.md
```

When a review note exists or a new review note appears:

1. Read the full review note.
2. If the note ends with:

   ```text
   STATUS: CHANGES_REQUESTED
   ```

   then resume work.

3. Clear the round-complete marker:

   ```bash
   scripts/orchestration/clear-finished fuzzy-sql-intellisense
   ```

4. Address every requested change.
5. Run quality gates:

   ```bash
   scripts/orchestration/run-quality-gates
   scripts/orchestration/check-review-notes-not-deleted
   ```

6. Commit code/docs fixes.
7. Commit the review-note file itself if it is not already committed:

   ```bash
   git add docs/review/fuzzy-sql-intellisense-review-*.md
   git commit -m "docs(review): record fuzzy-sql-intellisense review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished fuzzy-sql-intellisense
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer fuzzy-sql-intellisense` after the next review note is created.

---

## Approval Handling

If the latest review note ends with:

```text
STATUS: APPROVED
```

then:

1. Confirm every previous review item has been addressed.
2. Confirm all review notes are committed:

   ```bash
   scripts/orchestration/check-review-notes-committed fuzzy-sql-intellisense
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize fuzzy-sql-intellisense
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/fuzzy-sql-intellisense_finalized
   ```

6. Stop polling and exit cleanly.

---

## Review Rules

Do not write your own review.

Do not create files under:

```text
docs/review/
```

Do not delete files under:

```text
docs/review/
```

Only the orchestrator writes review notes. Your job is to read them, resolve them, commit them as audit records, and continue the loop.

---

## Finalization Rules

Only finalize after a review note with:

```text
STATUS: APPROVED
```

Finalization is performed with:

```bash
scripts/orchestration/finalize fuzzy-sql-intellisense
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/fuzzy-sql-intellisense_finished
/tmp/wherewolf/fuzzy-sql-intellisense_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
