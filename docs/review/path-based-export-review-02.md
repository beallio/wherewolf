# Review — path-based-export (round 02)

Branch: `feat/path-based-export` @ `b9b832c`
Reviewed against: `docs/plans/2026-08-01_path-based-export.md` and review 01

## Verdict

APPROVED.

H1–H4 are resolved. H5 is substantially improved and not worth another round.

## H1 — the exit criterion is now guarded, verified by counterfactual

Round 01's finding was that the whole suite passed while full export materialised the entire
result. I re-applied that exact mutation — `con.sql(...).pl()` in place of the `COPY ... TO` —
and the guard now fires:

```text
FAILED tests/test_full_export.py::test_full_export_issues_copy_without_materialising_result[csv]
FAILED tests/test_full_export.py::test_full_export_issues_copy_without_materialising_result[parquet]
2 failed, 350 passed
```

Parametrized across both formats, and it asserts the property rather than the output file —
which is what makes it able to fail. The exit criterion is now defended against regression, not
merely satisfied today.

## H2, H3, H4 — resolved

- **H2 cancellation** — `test_export_controller.py` now asserts the destination survives
  byte-identical (`destination.read_bytes() == b"original"`), **no temp file remains**
  (`list(tmp_path.glob(".out.csv.*")) == []`), cancelling a finished export is safe
  (`controller.cancel() is False`), the handle is published before work, and a failure is a
  terminal result rather than an exception.
- **H3 duplication removed** — `services/selection.py` is now the single implementation, and I
  verified by identity rather than by reading imports:

  ```text
  old top-level selection.py removed
  clipboard uses shared: True
  preview uses shared  : True
  ```

  Both call sites resolve to the *same function objects*, so copy and export cannot drift apart.
- **H4 mutations** — all six recorded with observed failure nodes.

## H5 — good enough

Round 02 produced five commits along review-item lines rather than one lump. `bf94cc3` still
combines Tasks 9 and 10 coverage. That is a marked improvement and I am not spending a round on
commit shape.

## Final state — measured by review

| check | result |
|---|---|
| suite on **3.14** | 352 passed, 1 skipped |
| suite on **3.12** | 352 passed, 1 skipped — identical |
| `run-quality-gates` | pass |
| **V11** crash gate 25 + 25 | **0 native crashes / 50** |
| **V9** 3.14-only syntax | none |
| **V2** Streamlit + `export/` diff | empty |
| H1 mutation (materialise) | **now bites** — was the defect |
| shared selection identity | same function objects |
| `git status --short` | clean |

## What this phase delivered

Path-based export for the desktop: destination normalization, atomic writes, preview writers
for CSV/XLSX/Parquet, selection export in visual order, **full export streamed through DuckDB
`COPY`**, an XLSX size guard, source-change warnings, an export controller with cancellation,
a native save dialog, and progress/cancel wiring with `shutdown()` in `closeEvent`.

The exit criteria hold: exported files reopen and match rows/columns/order; full export does not
materialise the result; a failed export leaves the destination byte-identical.

## Note on process

Round 01's session log recorded **"not measured"** for the mutations and crash batches instead
of inventing them. That honesty is what made this review efficient — it told me exactly where to
look, and the one real defect was found in the first place I checked. It is worth repeating that
this is the desired behaviour, not a shortfall.

## Deferred — correctly recorded

No human has exported from a real window; all Qt tests are offscreen. **Streaming is verified
structurally — a `COPY` is issued and no materialisation call occurs — not by a memory
measurement**; no multi-gigabyte export was performed. Spark export unverified. macOS and
Windows save dialogs unverified. Phase 13 is Spark, Phase 14 removes Streamlit.

STATUS: APPROVED
