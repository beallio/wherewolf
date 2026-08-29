# Plan: Edit menu text case formatting (edit-format-text)

## Context

Add an **Edit ▸ Format Text** submenu with six case transforms: `lowercase`, `UPPERCASE`,
`Title Case`, `camelCase`, `snake_case`, `kebab-case`. This is item **5** of a five-item user
report. Items 1, 3a, 3c and 4 are already merged; item **3b** (dataset multi-select batch
actions) is a separate plan and is not touched here.

The GUI is **PyQt6 + QScintilla**, not PySide6. There is no `QTextCursor`, `insertPlainText`,
`beginEditBlock`, or `endEditBlock` anywhere in `src/` — the editor is `SqlEditor`
(`src/wherewolf/desktop/widgets/sql_editor.py:32`), a `QsciScintilla` subclass. It supports a
**single** selection only; there is no multi-cursor support and none is to be added.

### Nothing like this exists yet

Verified absent from `src/`: `camel`, `snake`, `kebab`, `capitalize`, `swapcase`. Every
`.upper()`/`.lower()`/`.title()` hit is unrelated — SQL keyword handling in the completer,
dialect display labels, `casefold` alias normalisation, and window-title suffixes.

Do **not** confuse this with the existing SQL pretty-printer:
`SqlFormattingService.format_sql` (`src/wherewolf/services/formatting_service.py`) wraps
`sqlglot.transpile(pretty=True)` and is surfaced as "Format SQL" in the **Query** menu. It is a
different feature and must be left alone.

### User decisions (already made — do not re-litigate)

1. **Empty selection → operate on the current word under the caret.**
2. **Multi-line selection → transform line by line.**

### Two transform families

The six transforms are not uniform, and conflating them produces wrong output. Split them:

**Case-only** — preserve every separator and the overall structure:

- `lowercase` — `text.lower()`
- `UPPERCASE` — `text.upper()`
- `Title Case` — capitalise the first character of each alphanumeric run, lowercase the rest,
  leaving all separators exactly as they are

**Identifier-style** — re-segment into words and rejoin with a new separator:

- `camelCase`, `snake_case`, `kebab-case`

### Required behaviour table

This is the contract. Implement to this table; the tests must assert these exact values.

| input | lowercase | UPPERCASE | Title Case | camelCase | snake_case | kebab-case |
| --- | --- | --- | --- | --- | --- | --- |
| `customer_order_id` | `customer_order_id` | `CUSTOMER_ORDER_ID` | `Customer_Order_Id` | `customerOrderId` | `customer_order_id` | `customer-order-id` |
| `customerOrderId` | `customerorderid` | `CUSTOMERORDERID` | `Customerorderid` | `customerOrderId` | `customer_order_id` | `customer-order-id` |
| `HTTPResponseCode` | `httpresponsecode` | `HTTPRESPONSECODE` | `Httpresponsecode` | `httpResponseCode` | `http_response_code` | `http-response-code` |
| `total sales 2026` | `total sales 2026` | `TOTAL SALES 2026` | `Total Sales 2026` | `totalSales2026` | `total_sales_2026` | `total-sales-2026` |
| `SCREAMING_SNAKE` | `screaming_snake` | `SCREAMING_SNAKE` | `Screaming_Snake` | `screamingSnake` | `screaming_snake` | `screaming-snake` |
| `kebab-case-name` | `kebab-case-name` | `KEBAB-CASE-NAME` | `Kebab-Case-Name` | `kebabCaseName` | `kebab_case_name` | `kebab-case-name` |
| `order2id` | `order2id` | `ORDER2ID` | `Order2id` | `order2id` | `order2id` | `order2id` |

Note `customerOrderId` → `lowercase` → `customerorderid` is **correct**: a case-only transform
is exactly `.lower()` and is intentionally lossy. Likewise `Title Case` on a single
alphanumeric run yields one capital. Do not "improve" case-only transforms by tokenising them.

**The `order2id` row is the discriminating case for `Title Case` and must not be dropped.**
Python's `str.title()` treats a digit as a word boundary and returns `Order2Id`, whereas this
specification treats `order2id` as a single alphanumeric run and requires `Order2id`. Verified:
`"order2id".title()` is `'Order2Id'`. `str.title()` happens to agree with every other row of the
Title Case column, so without this row a naive `return text.title()` would pass the whole suite.

### Word segmentation rules (identifier-style only)

Split the input into tokens by, in order:

1. Discarding runs of characters that are neither letters nor digits (`_`, `-`, space, `.`, …);
   each such run is a token boundary.
2. Splitting at a lowercase→uppercase transition: `fooBar` → `foo`, `Bar`.
3. Splitting an uppercase run that is followed by uppercase+lowercase, so the final uppercase
   letter starts the next token: `HTTPResponse` → `HTTP`, `Response`.
4. Keeping digits attached to the token they occur in — `order2id` is one token. Do not split on
   letter↔digit transitions.

Then join: `snake_case` with `_` and `kebab-case` with `-`, both fully lowercased; `camelCase`
as the first token lowercased plus each later token as `token[:1].upper() + token[1:].lower()`.

### Current-word resolution, and its one sharp edge

Use QScintilla's own word boundaries: `SCI_WORDSTARTPOSITION` and `SCI_WORDENDPOSITION` with
`onlyWordCharacters=True`. Measured word characters for this editor:

| Character | Word char? |
| --- | --- |
| `_` underscore | **yes** |
| digits `0-9` | **yes** |
| `-` hyphen | **no** |
| `.` period | **no** |

Measured consequences, all verified against the running widget:

| Document | Caret offset | Current word |
| --- | --- | --- |
| `customer_order_id` | 3 or 12 | `customer_order_id` (whole identifier) |
| `SELECT customerOrderId FROM t` | 12 | `customerOrderId` |
| `SELECT * FROM my_table` | 18 | `my_table` |
| `order2id` | 6 | `order2id` |
| `  indented_word  ` | 6 | `indented_word` |
| `kebab-case-name` | 2 | `kebab` **only** |
| `"quoted col"` | 3 | `quoted` only |
| `SELECT  FROM t` (caret in the gap) | 7 | empty string |

**The hyphen behaviour is deliberate and must not be "fixed".** In SQL `-` is the subtraction
operator, so widening the current word across it would let `total-discount` be silently
rewritten to `totalDiscount`, corrupting an expression into an identifier. Kebab-cased text
must be **selected** to be converted; that is an accepted limitation to document, not a defect.

An empty current word (caret in whitespace, no selection) is a **no-op**: change nothing, and
leave the document and the undo stack untouched.

### Line-by-line transformation requirements

`selectedText()` returns the raw document text for the selection, and a selection may start and
end mid-line — measured: selecting `(0, 6)` to `(1, 4)` of `alpha_one\nbeta_two\n…` yields
`'one\nbeta'`. Two things therefore must not be broken:

1. **Preserve line terminators exactly.** Split so that `\r\n`, `\r` and `\n` survive verbatim.
   A naive `text.split("\n")` leaves a trailing `\r`, which the tokeniser would treat as a
   separator and discard, silently converting the file's line endings.
2. **Preserve each line's leading and trailing whitespace.** Transform only the stripped core of
   each line. Otherwise the identifier transforms eat indentation, because whitespace is a
   token boundary.

### Keyboard shortcuts — DBeaver parity

DBeaver **does** bind case conversion, in the **Text Editor** section of its shortcut reference
(<https://dbeaver.com/docs/dbeaver/Shortcuts/>):

| DBeaver Windows/Linux | macOS | DBeaver action |
| --- | --- | --- |
| `Ctrl+Shift+X` | `⇧⌘X` | Changes the selection to uppercase |
| `Ctrl+Shift+Y` | `⇧⌘Y` | Changes the selection to lowercase |

DBeaver defines no shortcut for Title Case, camelCase, snake_case or kebab-case — it has no such
commands. For those four, use the same `Ctrl+Shift+<letter>` family with mnemonic letters
verified free. (Note this app already matches DBeaver on `Ctrl+Shift+F` for Format SQL and
`Ctrl+/` for Toggle Comment.)

**Assign exactly these:**

| Menu label | Primary shortcut | Additional shortcut | Source |
| --- | --- | --- | --- |
| `lowercase` | `Ctrl+Shift+Y` | `Ctrl+U` | DBeaver parity + reclaimed QScintilla binding |
| `UPPERCASE` | `Ctrl+Shift+X` | `Ctrl+Shift+U` | DBeaver parity + reclaimed QScintilla binding |
| `Title Case` | `Ctrl+Shift+C` | — | free; mnemonic "Case" |
| `camelCase` | `Ctrl+Shift+M` | — | free; mnemonic "caMel" |
| `snake_case` | `Ctrl+Shift+N` | — | free; mnemonic "sNake" |
| `kebab-case` | `Ctrl+Shift+K` | — | free; mnemonic "Kebab" |

Use `QAction.setShortcuts([...])` for the two that have a second binding; the menu displays the
first. Use `setShortcut(...)` for the other four.

**All six were verified to actually fire with focus inside the QScintilla editor.** This matters:
QScintilla accepts `ShortcutOverride` for every key in its own command set, which is why this
repo already carries `_RELEASED_SCINTILLA_SHORTCUTS` machinery (`sql_editor.py:29`) — see
`docs/plans/2026-08-19_scintilla-shortcut-collisions.md`. Measured against
`editor.standardCommands()`:

| Candidate | In QsciCommandSet? | In app menus? | Keystroke result |
| --- | --- | --- | --- |
| `Ctrl+Shift+X` | free | free | **FIRED** |
| `Ctrl+Shift+Y` | free | free | **FIRED** |
| `Ctrl+Shift+C` | free | free | **FIRED** |
| `Ctrl+Shift+M` | free | free | **FIRED** |
| `Ctrl+Shift+N` | free | free | **FIRED** |
| `Ctrl+Shift+K` | free | free | **FIRED** |
| `Ctrl+Shift+L` | **bound** — Delete current line | free | do not use |
| `Ctrl+Shift+T` | **bound** — Copy current line | free | do not use |

### Reclaim QScintilla's two hidden case commands

QScintilla already ships live, undocumented case bindings that this feature must absorb rather
than duplicate. Measured from `editor.standardCommands()` — these are the only two QsciCommands
whose description mentions case:

| Key | QsciCommand |
| --- | --- |
| `Ctrl+U` | `Convert selection to lower case` |
| `Ctrl+Shift+U` | `Convert selection to upper case` |

They are selection-only: they do nothing with an empty selection, so they have no current-word
fallback and no line-by-line behaviour. Leaving them in place would give the user two keys per
case transform with **different semantics**, which is worse than either alone.

Add both sequences to `_RELEASED_SCINTILLA_SHORTCUTS` (`sql_editor.py:29`) so
`_release_conflicting_scintilla_keys` unbinds them, then re-bind them as the *additional*
shortcuts on the `lowercase` and `UPPERCASE` actions per the table above. Net effect: the user
keeps both muscle memories, and every case key now goes through one implementation with
consistent selection / current-word / line-by-line behaviour. Nothing is lost.

Shortcuts are a desktop concern. `QKeySequence` must **not** appear in
`src/wherewolf/services/text_case.py`; keep the shortcut mapping in the desktop layer, keyed by
the same labels `TEXT_CASE_TRANSFORMS` provides.

### One existing test will break, and that is authorised

`tests/test_main_window.py:1756-1780`
(`test_main_window_edit_menu_exposes_the_editor_actions`) asserts an **exact ordered list** of
non-separator Edit menu action texts:

```python
    actions = [action for action in window.edit_menu.actions() if not action.isSeparator()]
    assert [action.text() for action in actions] == [
        "Undo", "Redo", "Cut", "Copy", "Paste", "Select All",
        "Find / Replace…", "Toggle Comment", "Clear History",
    ]
```

`edit_menu.addMenu(...)` inserts the submenu's `menuAction()`, which is not a separator, so it
will appear in that list. **This plan authorises adding `"Format Text"` to the expected list at
the correct position** — an extension driven by the plan, not a weakening. Record the rationale
in the session log. Do not change any other assertion in that test.

### Non-goals

- No changes to `SqlFormattingService`, the Query menu's "Format SQL", or `sqlglot` usage.
- No multi-cursor or multi-selection support; no `SCI_SETADDITIONAL*` calls.
- No shortcut may be assigned outside the verified-free set above; in particular never
  `Ctrl+Shift+L` or `Ctrl+Shift+T`, which QScintilla owns.
- No widening of QScintilla's word characters, and no custom word scanner spanning `-` or `.`.
- No change to `_selected_text_range`, `text_to_run`, `toggle_comment`, or
  `format_selection_or_statement`.
- Items 2 and 3b of the original report are not in this plan.

**Slug used throughout this plan:** `edit-format-text`

---

## Orchestration Contract

**Slug:** `edit-format-text`

**Plan file:**

```text
docs/plans/2026-08-28_edit-format-text.md
```

**Implementation branch:**

```text
feat/edit-format-text
```

**Round-complete marker:**

```text
/tmp/wherewolf/edit-format-text_finished
```

**Finalized marker:**

```text
/tmp/wherewolf/edit-format-text_finalized
```

**Review notes:**

```text
docs/review/edit-format-text-review-*.md
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
git checkout -b feat/edit-format-text
```

Commit this plan first:

```bash
git add docs/plans/2026-08-28_edit-format-text.md
git commit -m "docs(plan): add edit-format-text implementation plan"
```

---

## Implementation Tasks

Work in order. All commands run from the repository root through the wrapper, e.g.
`./run.sh uv run pytest tests/test_text_case.py`. Follow Red-Green-Refactor: write the failing
test first and record the observed failure before the production change. Commit atomically with
Conventional Commits.

Build bottom-up: the pure string layer first with no Qt involved, then the editor method, then
the menu. Each layer is independently verifiable.

### Task 1 (RED) — failing tests for the pure transform layer

Create `tests/test_text_case.py`. Follow the convention of `tests/test_completion_matching.py`:
import the module directly (`from wherewolf.services.text_case import ...`); it does **not**
need to be re-exported from `src/wherewolf/services/__init__.py`, which does not import
`completion_matching` either. No `qtbot`, no Qt imports — this layer is pure.

Write tests for:

1. `test_split_words_segments_every_identifier_style` — parametrise over the segmentation rules:
   `customer_order_id` → `("customer", "order", "id")`; `fooBar` → `("foo", "Bar")`;
   `HTTPResponseCode` → `("HTTP", "Response", "Code")`; `total sales 2026` →
   `("total", "sales", "2026")`; `order2id` → `("order2id",)`; `kebab-case-name` →
   `("kebab", "case", "name")`; `SCREAMING_SNAKE` → `("SCREAMING", "SNAKE")`;
   `""` → `()`; `"___"` → `()`.
2. `test_each_transform_matches_the_specified_behaviour` — parametrise over **every cell** of the
   Context's behaviour table: 7 inputs × 6 transforms = 42 cases. Do not sample, and do not omit
   the `order2id` row; the table is the contract and that row is the only one that discriminates
   `Title Case` from `str.title()`.
3. `test_transform_lines_preserves_line_terminators` — assert that `\r\n`, `\r` and `\n` survive
   verbatim. Use the mixed-terminator input `"a_b\r\nc_d\re_f\ng_h"` transformed to camelCase and
   expect exactly `"aB\r\ncD\reF\ngH"`: every line's content changes, every terminator is
   byte-identical, and no terminator is normalised to another form.
4. `test_transform_lines_preserves_indentation_and_trailing_whitespace` — e.g.
   `"    customer_id  "` to camelCase yields `"    customerId  "`. This is the test that catches
   the identifier transforms eating whitespace.
5. `test_transform_lines_leaves_blank_lines_untouched` — a selection containing an empty line and
   a whitespace-only line must come back byte-identical for those lines.
6. `test_text_case_transforms_registry_is_ordered_and_complete` — assert
   `list(TEXT_CASE_TRANSFORMS)` equals exactly
   `["lowercase", "UPPERCASE", "Title Case", "camelCase", "snake_case", "kebab-case"]`. This
   pins both the menu labels and their order, because the menu is built from this mapping.

Run `./run.sh uv run pytest tests/test_text_case.py -q` and record the failure (expected: import
error / module not found). Then proceed.

### Task 2 (GREEN) — the pure transform module

Create `src/wherewolf/services/text_case.py`. Mirror `services/completion_matching.py`: module
docstring, `from __future__ import annotations`, dependency-free, explicit `__all__` at the end.
No Qt imports and no imports from `wherewolf.desktop`.

Public surface:

```python
def split_words(text: str) -> tuple[str, ...]: ...
def to_lowercase(text: str) -> str: ...
def to_uppercase(text: str) -> str: ...
def to_title_case(text: str) -> str: ...
def to_camel_case(text: str) -> str: ...
def to_snake_case(text: str) -> str: ...
def to_kebab_case(text: str) -> str: ...
def transform_lines(text: str, transform: Callable[[str], str]) -> str: ...

TEXT_CASE_TRANSFORMS: Mapping[str, Callable[[str], str]]
```

Requirements:

- `TEXT_CASE_TRANSFORMS` is an ordered mapping from menu label to transform function, in the
  order pinned by Task 1 test 6. It is the single source of truth for the menu's labels and
  order — `MainWindow` must build the submenu by iterating it, not by repeating the labels.
- `to_title_case` capitalises the first character of each alphanumeric run and lowercases the
  rest, preserving all separators. Do not use `str.title()` blindly without checking it against
  the behaviour table — verify `customer_order_id` → `Customer_Order_Id` and
  `total sales 2026` → `Total Sales 2026`.
- `transform_lines` splits the text so line terminators are preserved verbatim (a
  `re.split` that captures `\r\n|\r|\n` is the straightforward approach), and for each line
  applies `transform` to the stripped core while re-attaching the original leading and trailing
  whitespace. A line whose stripped core is empty is returned unchanged.
- `split_words("")` and `split_words("___")` return `()`. Every identifier-style transform
  returns `""` for an input with no tokens — never raise `IndexError` on `tokens[0]`.

Run the file's tests and record tallies; all six must pass.

Commit: `feat(services): add text case transforms`.

### Task 3 (RED) — failing tests for the editor method

Add to `tests/test_sql_editor.py`, following the existing `qtbot.addWidget(editor)` harness.
Write tests for a new `SqlEditor.apply_text_case(transform)` method:

7. `test_apply_text_case_transforms_the_selection` — set `"select customer_order_id from t"`,
   select just `customer_order_id`, apply `to_camel_case`, assert the document becomes
   `"select customerOrderId from t"`.
8. `test_apply_text_case_transforms_the_current_word_when_nothing_is_selected` — set
   `"select customer_order_id from t"`, put the caret inside the identifier with
   `setCursorPosition`, apply `to_camel_case`, assert only that word changed.
9. `test_apply_text_case_transforms_a_multiline_selection_line_by_line` — select three
   snake_case lines, apply `to_camel_case`, assert each line was converted independently and the
   line count is unchanged.
10. `test_apply_text_case_preserves_indentation_in_a_multiline_selection` — indented lines keep
    their leading whitespace.
11. `test_apply_text_case_is_a_single_undo` — apply a transform, call `editor.undo()` once,
    assert the document equals the original exactly. Model this on the existing
    `test_sql_editor_toggle_comment_one_undo_restores_original_text`.
12. `test_apply_text_case_with_the_caret_in_whitespace_changes_nothing` — caret in a gap, no
    selection; assert the document is unchanged **and** that `editor.isModified()` is still
    `False` (i.e. no empty undo entry was pushed).

Run and record failures. Expected: all six fail on the missing method.

### Task 4 (GREEN) — the editor method

In `src/wherewolf/desktop/widgets/sql_editor.py`, add one method. Do **not** add six methods,
and do not modify `_selected_text_range`, `text_to_run`, `toggle_comment`, or
`format_selection_or_statement`.

```python
    def apply_text_case(self, transform: Callable[[str], str]) -> None:
        """Re-case the selection, or the word under the caret when nothing is selected."""
```

Behaviour:

1. If `self.hasSelectedText()` and the selection is non-empty, use `self.getSelection()` and
   `self.selectedText()`.
2. Otherwise resolve the current word from the caret with
   `self.SendScintilla(self.SCI_WORDSTARTPOSITION, position, True)` and
   `self.SendScintilla(self.SCI_WORDENDPOSITION, position, True)`, where `position` comes from
   `self.positionFromLineIndex(*self.getCursorPosition())`. Convert those offsets back with
   `self.lineIndexFromPosition(...)`, as `format_selection_or_statement` already does.
3. If the resolved range is empty, **return immediately** — no selection change, no undo action.
4. Compute the replacement with `transform_lines(text, transform)` from the services module.
   If it equals the original text, return without touching the document or the undo stack.
5. Otherwise `setSelection(...)` over the range, then `replaceSelectedText(...)`, wrapped in
   `self.beginUndoAction()` / `self.endUndoAction()` in a `try/finally`, matching
   `format_selection_or_statement:439-472`.

Import `transform_lines` from `wherewolf.services.text_case`. Note the existing import block
already pulls from `wherewolf.services`; add a separate `from wherewolf.services.text_case
import transform_lines` line and let ruff order it.

Run and record; tests 7-12 pass.

Commit: `feat(editor): re-case the selection or current word`.

### Task 5 (RED then GREEN) — the Edit ▸ Format Text submenu

In `tests/test_main_window.py`:

13. `test_main_window_edit_menu_has_a_format_text_submenu` — assert the Edit menu contains a
    submenu titled `Format Text` whose action texts equal `list(TEXT_CASE_TRANSFORMS)`.
14. `test_main_window_format_text_action_recases_the_current_editor` — select text in
    `window.editor`, trigger the `snake_case` action from the submenu, assert the document
    changed. Trigger via the submenu's own `QAction`, not by calling the slot directly, so the
    wiring is covered.
15. `test_main_window_format_text_actions_have_the_specified_shortcuts` — assert each of the six
    actions reports exactly the primary shortcut from the Context's table, and that `lowercase`
    and `UPPERCASE` each report **two** sequences via `action.shortcuts()`, including `Ctrl+U`
    and `Ctrl+Shift+U` respectively.
16. `test_main_window_format_text_shortcuts_fire_with_focus_in_the_editor` — parametrise over all
    six primary sequences. Show the window, `QTest.qWaitForWindowExposed`, focus
    `window.editor`, set text, `QTest.keyClick` the sequence, and assert the document was
    transformed. This is the test that proves QScintilla does not swallow the key via
    `ShortcutOverride`; asserting `shortcut().toString()` alone would not.
17. `test_sql_editor_releases_the_scintilla_case_commands` — extend or mirror the existing
    `test_sql_editor_releases_scintilla_keys_that_collide_with_app_shortcuts`
    (`tests/test_sql_editor.py`) to assert `Ctrl+U` and `Ctrl+Shift+U` are no longer bound in
    `editor.standardCommands()`, so the reclaim actually happened.

Then extend `test_main_window_edit_menu_exposes_the_editor_actions` (`:1756-1780`) by inserting
`"Format Text"` into the expected list between `"Find / Replace…"` and `"Toggle Comment"`.
Change nothing else in that test. This edit is authorised by the Context section.

In `src/wherewolf/desktop/main_window.py`, inside `_build_menus`, insert after line 2092
(`edit_menu.addAction(self.find_replace_action)`) and before the line 2093 separator:

```python
        self.format_text_menu = cast(QMenu, edit_menu.addMenu("Format Text"))
        self.format_text_menu.setObjectName("format_text_menu")
        self.format_text_actions: dict[str, QAction] = {}
        for label, transform in TEXT_CASE_TRANSFORMS.items():
            action = cast(QAction, self.format_text_menu.addAction(label))
            action.setShortcuts([QKeySequence(seq) for seq in _FORMAT_TEXT_SHORTCUTS[label]])
            action.triggered.connect(
                lambda _checked=False, transform=transform: self._apply_text_case(transform)
            )
            self.format_text_actions[label] = action
```

Define the shortcut map as a module-level private constant in `main_window.py` (not in the
services module), ordered to match `TEXT_CASE_TRANSFORMS`:

```python
_FORMAT_TEXT_SHORTCUTS: dict[str, tuple[str, ...]] = {
    "lowercase": ("Ctrl+Shift+Y", "Ctrl+U"),
    "UPPERCASE": ("Ctrl+Shift+X", "Ctrl+Shift+U"),
    "Title Case": ("Ctrl+Shift+C",),
    "camelCase": ("Ctrl+Shift+M",),
    "snake_case": ("Ctrl+Shift+N",),
    "kebab-case": ("Ctrl+Shift+K",),
}
```

Add a guard so the two mappings cannot drift — e.g. assert
`_FORMAT_TEXT_SHORTCUTS.keys() == TEXT_CASE_TRANSFORMS.keys()` once at menu build, mirroring the
`DEFAULT_COLUMN_WIDTHS` guard added in the dataset-columns plan.

Also add `"Ctrl+U"` and `"Ctrl+Shift+U"` to `_RELEASED_SCINTILLA_SHORTCUTS`
(`src/wherewolf/desktop/widgets/sql_editor.py:29`). That tuple currently holds `"Ctrl+T"` and the
Toggle Comment sequence; `_release_conflicting_scintilla_keys` already iterates it and clears both
`key()` and `alternateKey()`, so no new mechanism is needed.

The `lambda _checked=False, transform=transform:` default-argument binding is required — a bare
closure over the loop variable would give every action the last transform. This mirrors the
existing Edit-menu loop at `main_window.py:2074-2084`.

Add the slot next to `_run_current_editor_action` (`:2019-2023`), mirroring its editor guard:

```python
    def _apply_text_case(self, transform: Callable[[str], str]) -> None:
        editor = self.current_editor
        if editor is not None:
            editor.apply_text_case(transform)
```

Do **not** route this through `_run_current_editor_action` (which does
`getattr(editor, operation)()` and cannot pass an argument) or through
`_dispatch_focused_edit_action` (which walks focus parents and is for native widget edit verbs).

Run the file and record tallies. Tests 13-15 and the extended action-list test all pass.

Commit: `feat(desktop): add an Edit Format Text submenu`.

### Task 6 — documentation and session log

- Add a `### Added` entry under the existing `## Unreleased` heading in `CHANGELOG.md`, in the
  user-visible prose style of the released sections. Mention that it acts on the selection or the
  word under the caret, that multi-line selections are converted line by line, and **list the six
  keyboard shortcuts**. Note the `Ctrl+Shift+X` / `Ctrl+Shift+Y` pair matches DBeaver. Also state
  the kebab-in-current-word limitation, since a user will hit it. Add a `### Changed` note that
  QScintilla's built-in `Ctrl+U` / `Ctrl+Shift+U` case keys now route through the new actions, so
  they gain the current-word and line-by-line behaviour.
- Update `README.md` only if it documents editor menus; check first.
- Write the session log required by `AGENTS.md` §14 to
  `docs/agent_conversations/2026-08-28_edit-format-text.json`: date, objective, files modified
  (**including this plan file**), tests added, design decisions — specifically why one
  `apply_text_case(transform)` method rather than six, why `TEXT_CASE_TRANSFORMS` is the single
  source of the menu labels, the DBeaver-parity basis for `Ctrl+Shift+X` / `Ctrl+Shift+Y` and the
  mnemonic basis for the other four, why QScintilla's `Ctrl+U` / `Ctrl+Shift+U` were reclaimed
  rather than left in place, and the rationale for extending the Edit-menu action-list test — and
  results. List every commit sha you created.

Commit: `docs: record edit-format-text changes`.

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

Run after the Quality Gates above pass. Every step must be able to fail; see
`references/verification-standards.md`. Record **actual output** — tallies, failing test names,
observed values — never a bare conclusion.

### V1 — mutation: prove the behaviour table is enforced

Temporarily change `to_title_case` to `return text.title()` and run:

```bash
./run.sh uv run pytest tests/test_text_case.py -q
```

Expected failure: **only the `order2id` Title Case case fails**, with expected `Order2id` and
actual `Order2Id`. Verified: `str.title()` agrees with every other row of the Title Case column,
which is exactly why that row exists. Record the expected-vs-actual strings. If nothing fails,
the `order2id` row was dropped from the parametrisation — restore it before continuing. Restore
the implementation afterwards.

### V2 — mutation: prove terminator and whitespace preservation are enforced

Temporarily reimplement `transform_lines` as
`"\n".join(transform(line) for line in text.split("\n"))` — the naive version — and run the same
file.

Expected failure: `test_transform_lines_preserves_line_terminators` fails (a `\r\n` input comes
back as `\n`, or a stray `\r` is swallowed by the tokeniser), and
`test_transform_lines_preserves_indentation_and_trailing_whitespace` fails (indentation eaten).
Record both, with the actual returned strings. Restore.

### V3 — mutation: prove the current-word path and the no-op guard

Two separate mutations, each run and recorded:

1. Make `apply_text_case` return early when there is no selection (drop the current-word
   branch). Expected: `test_apply_text_case_transforms_the_current_word_when_nothing_is_selected`
   fails.
2. Remove the empty-range early return, so an empty current word still opens an undo action and
   replaces an empty selection. Expected:
   `test_apply_text_case_with_the_caret_in_whitespace_changes_nothing` fails on the
   `isModified()` assertion.

If mutation 2 leaves everything green, the no-op guard is untested — fix the test. Restore both.

### V4 — mutation: prove the menu wiring, not just the slot

Temporarily change the submenu loop's lambda to close over the loop variable directly
(`lambda _checked=False: self._apply_text_case(transform)`), reintroducing the classic
late-binding bug where every action applies the **last** transform.

Expected failure: `test_main_window_format_text_action_recases_the_current_editor` fails, because
triggering the `snake_case` action applies `kebab-case` instead. If it still passes, that test is
triggering the wrong thing or asserting too loosely — likely it calls the slot directly instead
of the QAction. Fix it. Restore.

### V5 — mutation: prove the shortcuts are live, not merely declared

Two separate mutations, each run and recorded.

1. Change `UPPERCASE`'s primary shortcut from `Ctrl+Shift+X` to `Ctrl+Shift+L`, which QScintilla
   owns (`Delete current line`). Run
   `./run.sh uv run pytest tests/test_main_window.py -q -k "format_text_shortcuts"`.
   Expected failure: the `UPPERCASE` case of
   `test_main_window_format_text_shortcuts_fire_with_focus_in_the_editor` fails because
   QScintilla claims the key via `ShortcutOverride` — and note whether the document instead lost
   a line, which is the visible symptom of the collision. If it still passes, that test is not
   actually sending a keystroke to a focused editor; fix it before continuing.
2. Remove `"Ctrl+U"` and `"Ctrl+Shift+U"` from `_RELEASED_SCINTILLA_SHORTCUTS`. Expected failure:
   `test_sql_editor_releases_the_scintilla_case_commands` fails, and the `lowercase` /
   `UPPERCASE` additional-shortcut assertions in
   `test_main_window_format_text_actions_have_the_specified_shortcuts` may also fail. Record
   which. This proves the reclaim is real rather than decorative.

Restore both.

### V6 — negative control: full suite

Runs **after** V1-V5 so it cannot pass merely because nothing was exercised. Run each command
separately; do not chain with `&&` and do not pipe, so no failure is masked:

```bash
./run.sh uv run ruff check .
./run.sh uv run ruff format --check .
./run.sh uv run ty check src/
./run.sh uv run pytest
```

Record each exit status and the pytest pass/fail/skip tallies. The suite was **891 passed, 9
deselected** before this plan; report the new totals and account for the difference by the number
of tests you added. Note the Spark tier is deselected by the default `-m 'not spark'` addopts.

### V7 — observed-value check on the six transforms

Print real strings rather than asserting a boolean. In a scratch script under `/tmp/wherewolf/`
(do not commit it), import the six transforms and print a row per input for
`customer_order_id`, `HTTPResponseCode` and `total sales 2026`.

Expected output must match the Context's behaviour table exactly. Paste the printed table into
the session log, then delete the script.

### Deferred and unverified

State these explicitly in the session log; do not claim them as verified:

- **On-screen confirmation is deferred.** Everything runs under `QT_QPA_PLATFORM=offscreen`
  (`tests/conftest.py:14`). That proves menu structure, action wiring, shortcut delivery, document
  text and undo behaviour, but not that the submenu renders and cascades correctly on a real
  display, nor that shortcut labels appear correctly in the menu. The user
  must confirm on a windowed session by launching `./run.sh uv run wherewolf-desktop`, selecting
  text, and walking Edit ▸ Format Text through all six entries.
- **Kebab-cased text is not reachable via the current-word path**, because `-` is not a
  QScintilla word character. This is intentional (it protects `total-discount` arithmetic from
  being rewritten as an identifier) and is documented in the CHANGELOG rather than fixed.
- **Non-ASCII range handling is tested.** The current-word path reads QScintilla's selected
  range rather than slicing a Python string with Scintilla byte positions. Regression tests cover
  a non-ASCII character before the word, within the word, and in the selection path. The
  transforms' Unicode case mapping remains Python's `str.lower()`/`str.upper()` behaviour; no
  broader Unicode behaviour table is pinned.
- **No multi-cursor support.** The editor has a single selection only; applying a transform to
  several disjoint ranges at once is not possible and is out of scope.

---

## Mark Round Complete

When the implementation round is complete and the working tree is clean, run:

```bash
scripts/orchestration/mark-finished edit-format-text
```

This writes:

```text
/tmp/wherewolf/edit-format-text_finished
```

Then exit cleanly. If this process exits, the orchestrator will resume you through
`scripts/orchestration/continue-implementer edit-format-text`.

---

## Review Polling Loop

After marking the round complete, check existing review notes first, then poll for new review notes if you remain active:

```text
docs/review/edit-format-text-review-*.md
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
   scripts/orchestration/clear-finished edit-format-text
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
   git add docs/review/edit-format-text-review-*.md
   git commit -m "docs(review): record edit-format-text review notes"
   ```

8. Recreate the round-complete marker:

   ```bash
   scripts/orchestration/mark-finished edit-format-text
   ```

9. Either continue polling or exit cleanly. If you exit, the orchestrator will resume you with `scripts/orchestration/continue-implementer edit-format-text` after the next review note is created.

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
   scripts/orchestration/check-review-notes-committed edit-format-text
   ```

3. Confirm the working tree is clean:

   ```bash
   git status --short
   ```

4. Finalize:

   ```bash
   scripts/orchestration/finalize edit-format-text
   ```

5. Confirm the finalized marker exists:

   ```text
   /tmp/wherewolf/edit-format-text_finalized
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
scripts/orchestration/finalize edit-format-text
```

Do not manually merge into `dev` unless the finalize script fails and the user/orchestrator explicitly instructs you to recover manually.

Leave both markers in place after finalization:

```text
/tmp/wherewolf/edit-format-text_finished
/tmp/wherewolf/edit-format-text_finalized
```

Any project-specific release step runs from the project's
`scripts/orchestration-hooks/finalize-release` hook, invoked by finalize.
