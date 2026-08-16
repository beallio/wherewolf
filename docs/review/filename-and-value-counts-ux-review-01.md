# Review 01 — filename-and-value-counts-ux

**Branch:** `feat/filename-and-value-counts-ux`
**Head reviewed:** `6582bb2`
**Base:** `dev`
**Gates as re-run by the reviewer:** `554 passed, 7 deselected`, coverage 90% (baseline on `dev` was `547 passed`, 90%).

## Summary

The three units are implemented and structurally match the plan. All five V6 mutations
were re-run independently by the reviewer and every one turns its suite red, so the
suite is load-bearing rather than decorative. Two findings block the round: one is a
real runtime defect that means Defect C is not actually fixed, and one is a test that
cannot detect a regression of Defect A.

Reviewer-verified mutation results (re-measured, not taken from the session log):

| Mutation | Result |
|---|---|
| 1 — column 1 returns `str(entry.path)` | `1 failed, 21 passed` |
| 2 — File section back to `Stretch` | `2 failed, 16 passed` |
| 3 — drop `ElideLeft` in the delegate | `1 failed, 1 passed` |
| 4 — restore `max(22, ...)` compression | `1 failed, 7 passed` |
| 5 — reconnect `valueChanged` to `_run_worker` | `1 failed, 7 passed` |

---

## MECHANICAL — must fix

### M1. The debounce interval is overwritten by the spinbox value

`src/wherewolf/desktop/widgets/value_counts_window.py:165`

```python
self.limit_selector.valueChanged.connect(self._limit_debounce.start)
```

`QSpinBox.valueChanged` emits an `int`, and `QTimer.start` is overloaded as
`start()` and `start(int msec)`. The connection therefore binds to the
`start(msec)` overload and the emitted **Top N value becomes the timer interval**,
permanently replacing the `setInterval(self.DEBOUNCE_MS)` set three lines earlier.
`DEBOUNCE_MS` is dead after the first spinbox change.

Measured directly against this wiring:

```text
configured interval            : 300
after setValue(10)   -> interval: 10
after setValue(5000) -> interval: 5000
```

Consequences, both user-visible:

- At small Top N the debounce effectively disappears. At Top N = 10 the window is
  10 ms, so arrow-clicking still starts a worker per click — **Defect C is not fixed
  for exactly the case the plan described** ("clicking the up-arrow from 50 to 60
  launches ten concurrent scans").
- At large Top N it becomes a stall. At Top N = 5000 the user waits five seconds
  after they stop adjusting before anything happens, which reads as a hang. This is a
  regression the pre-fix code did not have.

The existing test passes anyway because the three `setValue` calls in
`test_value_counts_window_debounces_rapid_limit_changes` run synchronously within one
event-loop iteration, so the timer restarts before firing at *any* interval. The test
is insensitive to the bug.

**Exact replacement:**

```python
self.limit_selector.valueChanged.connect(lambda _value: self._limit_debounce.start())
```

Reviewer-verified — with this form the interval stays `300` across
`setValue(10)`, `setValue(5000)`, and `setValue(1)`, and the timer is active after
each.

**Also add a test that fails against the current code.** The coalescing test cannot
catch this; assert the interval directly:

```python
def test_value_counts_window_keeps_a_constant_debounce_interval(qtbot) -> None:
    window = ValueCountsWindow(_binding(), "category", _FakeRegistry(_FakeAdapter()))
    qtbot.addWidget(window)

    for value in (10, 5_000, 1):
        window.limit_selector.setValue(value)
        assert window._limit_debounce.interval() == ValueCountsWindow.DEBOUNCE_MS
```

### M2. The dock-level basename tests never read the model

`tests/test_catalog_dock.py:70-71` and `tests/test_catalog_dock.py:129-130`

Both tests compute the rendered string from a literal they construct themselves:

```python
first_shown = font_metrics.elidedText(first_path.name, view.textElideMode(), available_width)
```

`first_path.name` is the test's own value, not anything the model produced. Neither
test calls `model.data(index, DisplayRole)` or reads the view, so what they actually
assert is "a basename fits inside 220 px" — very nearly a tautology — rather than
"the File column displays the basename".

Reviewer-verified: with `catalog_model.py` mutated to return `str(entry.path)` from
column 1 — i.e. Defect A fully reintroduced —
`pytest tests/test_catalog_dock.py -k basename` reports **`2 passed`**. Only
`tests/test_catalog_model.py` catches the regression. These two tests would have
passed against the shipped-broken 0.8.0 build, which is the same failure mode that let
Defect A reach a release in the first place.

**Fix:** source the string under test from the model, so the assertion spans the real
path from `CatalogModel.data` to the rendered cell. For example:

```python
displayed = dock.model.data(dock.model.index(0, 1), Qt.ItemDataRole.DisplayRole)
first_shown = font_metrics.elidedText(displayed, view.textElideMode(), available_width)
assert first_path.name in first_shown
```

Apply the same change to both tests. After the change, re-run mutation 1 and confirm
`tests/test_catalog_dock.py` now goes red; record that output.

---

## MECHANICAL — minor

### M3. Vestigial assertion on a string the app no longer displays

`tests/test_catalog_dock.py:72-77,84-86`

`first_right` / `second_right` still right-elide `str(first_path)` and assert the two
are equal. The File column no longer displays full paths, so this documents nothing
about current behavior — it asserts a property of `QFontMetrics`. Either delete the
two `*_right` bindings and the `first_right == second_right` assertion, or repoint
them at the Folder column, where full-path elision is still the real behavior.

### M4. A dropped assertion was not replaced

`tests/test_catalog_dock.py:99-106` previously proved the File column grew when the
dock widened. That check was removed with the switch to `Interactive`, correctly, but
nothing replaced it for the Folder column, which now carries `Stretch`. Add the
equivalent narrow/wide growth assertion against section 2 so the stretch behavior
stays covered.

---

## DESIGN — author's call

### D1. The Windows path fixture is not a Windows path

`tests/test_catalog_dock.py:113-119` uses
`Path("C:/Users/dbeall/OneDrive - Contoso/Documents/Analytics/2026/customers.parquet")`.
On Linux this is a *relative* path whose first segment is `C:`, and
`CatalogService.add_paths` calls `.resolve()`, so the stored path is actually
`<repo>/C:/Users/.../customers.parquet`. `.name` is unaffected, so the test is sound —
but it is not exercising a Windows path, and the name implies otherwise.

The plan already lists "Windows 11 is not exercised" as a deferred item, so this is not
a blocker. Consider renaming the fixture variables, or using `PureWindowsPath` for the
string-shape assertions, so a later reader is not misled into thinking Windows
rendering is covered.

### D2. TDD ordering

`df5768f` and `cb0c050` are test commits landing after the implementation commits
`e58055f` / `f6d5808`. `cb0c050` ("harden fixed-row mutation check") reads as the
mutation gate correctly catching a weak test and the implementer strengthening it,
which is the process working. Note the ordering rationale in the session log rather
than leaving it to be inferred.

---

## Confirmed good

- `catalog_model.py` column remap is correct and `ToolTipRole` now covers columns 1
  and 2.
- Resize modes match the plan exactly, and `resizeSection(1, 400)` sticking at 400 is
  asserted behaviourally, which is the assertion that pins the original user
  complaint.
- The `paintEvent` culling arithmetic is correct at both edges. `(rect.top() - padding)
  // row_height` floors negative to `-1` and is clamped by `max(0, ...)`; when
  `rect.bottom() < padding`, `last` becomes `-1` and `range(first, last + 1)` is empty
  rather than raising. `maximum` is still computed across all counts, so bar scaling
  does not shift while scrolling.
- `dim_colour` is direction-preserving and tested in both light and dark orientations;
  leaving `HighlightedText` untouched keeps selected rows legible.
- `closeEvent` still stops every worker in `self._workers`, not just the current one.
- No measurement harness was left behind and the working tree is clean.

---

## Required before the next round

1. Fix M1 and add the interval test.
2. Fix M2 in both tests and re-run mutation 1 to show `test_catalog_dock.py` going red.
3. Address M3 and M4.
4. Re-run `scripts/orchestration/run-quality-gates` and record the tallies.

STATUS: CHANGES_REQUESTED
