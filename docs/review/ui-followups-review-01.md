# Review — ui-followups (round 01)

Branch: `feat/ui-followups` @ `7b6bbf0`
Reviewed against: `docs/plans/2026-08-02_ui-followups.md`

## Verdict

APPROVED. Six tasks, six commits plus docs.

## Gate status

```text
ruff check   All checks passed
ty check .   All checks passed
pytest       411 passed, 7 deselected   (was 408; +3 tests)
git status   clean
```

## F1 — the regression is fixed, and now tested the way it should have been

The controls were never deleted; they were hidden behind Qt's overflow extension whenever
the window was narrower than the toolbar's 1449px `sizeHint`. The fix moves the query
controls to their own toolbar row via `addToolBarBreak`. Measured with the window shown and
resized:

```text
1024px  all controls visible
1280px  all controls visible
1440px  all controls visible
1600px  all controls visible
QScrollArea count: 0
```

**Round 02's review asserted the controls existed and that no `QScrollArea` remained — it
never asserted they were visible.** `findChild` returns hidden widgets, so that check passed
against a toolbar the user experienced as empty. Visibility at multiple widths is now the
guard.

## F2–F4 — history

```text
timestamp column resize mode : ResizeMode.Interactive   (was ResizeToContents)
resizeSection(0, 240)        : 240px, takes effect
displayed timestamp          : '2026-08-01T15:03:35-07:00'
tooltip                      : '2026-08-01T15:03:35.069510-07:00'   (full value retained)
restore a history record     : editor -> 'SELECT 42', catalog -> ['keep'] UNCHANGED
```

`_restore_history_query` now sets the editor text and nothing else — no `add_paths`, no
queued schema work. The catalog-untouched assertion is the one that matches the actual
complaint.

## F5 — the completion popup

Diagnosed rather than rebuilt, as the plan required: the settings were already correct
(`DEFAULT_COMPLETION_ENABLED = True`, threshold 2) and `textChanged` was already wired. The
break was in delivery to Scintilla. After the fix, typing `cus` with a `customers` dataset
loaded leaves the list active:

```text
completion list active after typing 'cus': True
```

## F6 — errors in the results area

```text
after failure : ('result_error_message', 'Query failed: Binder Error: column bad not found', visible=True)
after success : []   (cleared)
```

Both directions checked — a fix that shows the error but never clears it would be worse
than the original.

## Negative controls — full suite, baseline 411

| mutation | result |
|---|---|
| F1: query controls back on the primary toolbar (no break) | 2 failed, 409 passed |
| F4: re-add `_restore_history_catalog(record)` | 2 failed, 409 passed |
| F5: `SCI_AUTOCSHOW` → `SCI_AUTOCCANCEL` | 2 failed, 409 passed |
| F6: error label never made visible | 1 failed, 410 passed |

**Every one of my first-attempt mutations failed to apply**: two regexes matched nothing and
one produced empty pytest output from a syntax error. All three initially looked like
passing guards. I located the real call sites (`main_window.py:441-447`,
`completion_adapter.py:70`, the `_restore_history_query` body) and re-ran with an explicit
"applied: True" check before recording anything. This is the fourth time this session the
pattern has appeared; the rule now stands in every plan — **prove the mutation changed the
code before believing its result.**

## The boundary held

Version `0.5.2`, no tag, `main` untouched. No `QScrollArea` reintroduced. `timid = true`,
the `pyarrow` import, the overwrite confirmation, `EngineKind` and the `DIALECT_MAPPING`
identifiers all unchanged.

## Deferred

Toolbar composition across two rows, and how the completion popup feels in real use, are
manual maintainer checks. The update check remains off by default and its enabled path is
still unexercised against a live network.

STATUS: APPROVED
