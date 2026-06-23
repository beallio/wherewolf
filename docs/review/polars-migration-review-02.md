# Review — polars-migration (round 02)

Branch reviewed: `feat/polars-migration`
Commit reviewed: `0a2c267`
Plan reviewed against: `docs/plans/2026-06-23_polars-migration.md`

## Final verdict

APPROVED. The migration is complete and correct. Polars is the canonical DataFrame type
across the application boundary (`QueryResult.df`, both engines, the schema HUD, and the
`Exporter`). The Spark engine is fully pandas-free via the public `toArrow()` API
(`pl.from_arrow(res.toArrow())` for collection, `pl.read_excel(...).to_arrow()` for Excel
ingestion, Arrow enabled on the session). DuckDB uses native `.pl()`. Exports use Polars
writers. `pandas` and `openpyxl` are removed as direct dependencies; `polars`, `fastexcel`,
and `xlsxwriter` are present. The `limit=None` full-export path is preserved.

## Gate status

- `scripts/orchestration/run-quality-gates`: PASS — ruff check/format clean, `ty check
  src/` clean, pytest 55 passed / 1 skipped.
- Working tree: clean.
- Review notes: none deleted.
- No `import pandas` / `pd.` / `.toPandas()` remain in `src/` or `tests/`.

## Prior findings — all resolved

1. README dependency list corrected — `pandas` and `openpyxl` removed; `polars`,
   `fastexcel`, `xlsxwriter` added (matches `pyproject.toml`). Resolved.
2. README export note updated to state DataFrame handling/exports are Polars-based. Resolved.
3. Session log added at `docs/agent_conversations/2026-06-23_polars-migration.json`
   (objective, files, decisions including the `toArrow()` choice, results). Resolved.
4. Nit: stale `# Mock limit and toPandas` comment now reads `toArrow`. Resolved.

## Finalization instructions

Finalize as the plan specifies — local merge into `main`, no release bump:

```bash
scripts/orchestration/finalize polars-migration
```

Do not pass a version-bump argument (the finalize-release hook is a no-op without one, so
no tag/push occurs). After finalize, confirm `/tmp/wherewolf/polars-migration_finalized`
exists, then exit cleanly.

STATUS: APPROVED
