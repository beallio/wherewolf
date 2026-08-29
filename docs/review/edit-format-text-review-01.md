# Review — edit-format-text (round 01)

Branch: `feat/edit-format-text`
Reviewed against: `docs/plans/2026-08-28_edit-format-text.md`
Reviewed at: `f80e7ff`

## Verdict

CHANGES_REQUESTED — one MAJOR defect. Everything else in the round is correct and several
things are better than the plan asked for.

`SqlEditor.apply_text_case` **silently corrupts the document** whenever any non-ASCII
character appears earlier in the document than the word being transformed. This is data
loss, not merely an unhandled case, so it blocks the round.

The plan listed non-ASCII input as "not specified or tested". That was a statement about
test coverage, not a licence to delete the user's characters. Reading the wrong slice is a
bug regardless of whether a test covered it.

## Gate status

Independently re-run by the orchestrator, each command separately (not chained, not piped):

| Command | Result |
| --- | --- |
| `ruff check .` | exit 0 |
| `ruff format --check .` | exit 0 |
| `ty check src/` | exit 0 |
| `pytest` | exit 0 — 961 passed, 9 deselected (Spark tier) |

Test count rose 891 → 961. Working tree clean. No files created or deleted under
`docs/review/`. Changed paths are exactly the nine the plan expects.

## Required changes

### 1. MAJOR — byte/character offset mismatch corrupts the document

`src/wherewolf/desktop/widgets/sql_editor.py:461`

```python
            text = self.text()[start:end]
```

`start` and `end` come from `SCI_WORDSTARTPOSITION` / `SCI_WORDENDPOSITION` (lines 455-456).
Scintilla positions are **byte** offsets into the UTF-8 document. `self.text()` is a Python
`str` indexed by **character**. The two disagree as soon as any multi-byte character occurs
earlier in the document.

The *range* is fine — `lineIndexFromPosition` (lines 459-460) converts correctly, so
`setSelection` at line 469 selects the right span. Only the text that gets *read and
transformed* is wrong, so the transform is applied to a shifted slice and then written over
the correct range.

Measured against the real widget:

| Input document | Caret | Actual result | Expected |
| --- | --- | --- | --- |
| `select café, customer_order_id from t` | in `customer_order_id`, camelCase | `select café, ustomerOrderId  from t` | `select café, customerOrderId from t` |
| `select café_total from t` | in `café_total`, UPPERCASE | `select CAFÉ_TOTAL  from t` | `select CAFÉ_TOTAL from t` |

Note the first row **loses the leading `c`** and gains a stray space. That is silent data
corruption in a SQL editor.

This is more likely to bite than "accented identifiers" suggests: positions are
document-wide, so a single non-ASCII character anywhere earlier — an em-dash in a `--`
comment, a currency symbol in a string literal, a `°` in a column alias — shifts every
subsequent current-word transform on every line below it.

The selection path (lines 449-451) is **already correct** because it reads
`self.selectedText()`. Verified: selecting `café_total` and applying UPPERCASE yields
`select CAFÉ_TOTAL from t` exactly.

**Fix requirement:** the text passed to `transform_lines` must be exactly the text the
replacement range covers. Do not paper over this with a byte-to-character conversion helper
computed from `self.text()`. Prefer eliminating the second text-reading path entirely so
both branches read the same way — for example resolve the range first, then `setSelection`
and read `selectedText()` for both branches, restoring the original caret/selection and
returning early when the replacement is unchanged. Any approach is acceptable provided the
regression tests below pass and the no-op guard still holds (see item 3).

### 2. MAJOR — add non-ASCII regression tests

Add to `tests/test_sql_editor.py`, alongside the existing `apply_text_case` tests:

1. `test_apply_text_case_current_word_is_correct_after_earlier_non_ascii` — document
   `"select café, customer_order_id from t"`, caret inside `customer_order_id`, apply
   camelCase, assert the document equals `"select café, customerOrderId from t"` exactly.
2. `test_apply_text_case_handles_non_ascii_inside_the_current_word` — document
   `"select café_total from t"`, caret inside `café_total`, apply UPPERCASE, assert
   `"select CAFÉ_TOTAL from t"` exactly.
3. `test_apply_text_case_selection_path_handles_non_ascii` — the selection branch with the
   same accented input, asserting the same result. This passes today; add it so the two
   branches stay in agreement.

Assert on the **whole document string**, not a substring — the observed failures manifested
as a dropped character plus a stray space, both of which a substring check would miss.

### 3. MINOR — keep the no-op guard provable after the fix

`test_apply_text_case_with_the_caret_in_whitespace_changes_nothing` currently proves the
no-op path via `_TextCaseNoOpSpyEditor`, asserting `begin_undo_calls == 0` and
`replace_selected_text_calls == 0` (`tests/test_sql_editor.py`). That spy is a genuine
improvement over the `isModified()` check the plan specified — keep it.

If the fix for item 1 moves `setSelection` before the `replacement == text` comparison, then
also assert that a no-op leaves the **caret position and selection state unchanged**, so the
restructure cannot introduce a visible side effect on an unchanged transform. Extend the
existing test or add one; do not weaken the existing zero-call assertions.

## Verified correct — no action needed

Recorded so the next round does not re-litigate these.

- **Behaviour table**: all 42 cells implemented as specified, including the `order2id` row
  that discriminates `Title Case` from `str.title()`.
- **Tokeniser** (`text_case.py:12-30`): `HTTPResponseCode` → `("HTTP", "Response", "Code")`
  via the upper-run-followed-by-lower rule; digits stay attached.
- **`transform_lines`** (`text_case.py:77-95`): terminators preserved via a capturing
  `re.split`; leading/trailing whitespace re-attached. Correctly guards the `[-0:]` trap at
  line 93 with `if trailing_length else ""` — a naive slice there would have returned the
  whole string.
- **Shortcuts**: `_FORMAT_TEXT_SHORTCUTS` matches the plan's table exactly, including the two
  additional sequences via `setShortcuts`. The `assert _FORMAT_TEXT_SHORTCUTS.keys() ==
  TEXT_CASE_TRANSFORMS.keys()` drift guard is present.
- **Scintilla reclaim**: `"Ctrl+U"` and `"Ctrl+Shift+U"` added to
  `_RELEASED_SCINTILLA_SHORTCUTS` (`sql_editor.py:28-33`).
- **Layering**: no `QKeySequence` in `services/text_case.py`; module is dependency-free with
  an explicit `__all__`.
- **Single method**: one `apply_text_case(transform)`, not six. `_selected_text_range`,
  `text_to_run`, `toggle_comment` and `format_selection_or_statement` untouched.
- **Late-binding**: the submenu loop uses `lambda _checked=False, transform=transform:`.
- **Authorised test edit**: `"Format Text"` added to the expected list in
  `test_main_window_edit_menu_exposes_the_editor_actions`; nothing else in that test changed.

The extra commit `8e10816` ("strengthen text case regression checks") is legitimate
self-improvement, not scope creep: it derives the keystroke from
`window.format_text_actions[label].shortcut()[0]` instead of hardcoding it, and adds the
undo/replace call-count spy. The exact expected sequences remain pinned by
`test_main_window_format_text_actions_have_the_specified_shortcuts`, so nothing was lost.

## On completing this round

Re-run the plan's verification steps that touch `apply_text_case` (V3 in particular) after
the fix, and record in the session log both the defect and the approach chosen for item 1.
Update the plan's "Deferred and unverified" claim about non-ASCII input: after this round,
non-ASCII is *handled and tested* for both branches, even though the transforms' own
behaviour on non-ASCII case mapping is still whatever Python's `str.lower()`/`str.upper()`
do.

STATUS: CHANGES_REQUESTED
