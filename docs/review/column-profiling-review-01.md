# Review — column-profiling (round 01)

Branch: `feat/column-profiling` @ `d6358ba` (+ `93f75b3`, an unrelated fix found during review)
Reviewed against: `docs/plans/2026-08-02_column-profiling.md`

## Verdict

APPROVED. Six tasks, six commits, one per task.

## Gate status

```text
ruff check   All checks passed
ty check .   All checks passed
pytest       420 passed, 7 deselected   (was 411; +9 tests)
git status   clean
```

**The first run showed 3 failures, and they were not caused by this change.** See
"Environmental failure" below — that finding is the most consequential thing in this review.

## Behaviour, measured by review

Profiling a purpose-built mixed-type CSV (100 rows: integer, float, VARCHAR, and a column
with exactly 25 nulls):

```text
profiled columns               ['n', 'f', 's', 'withnull']
VARCHAR 's'      avg           None            correct — not applicable
numeric 'n'      avg           49.5            correct for 0..99
'withnull'       null %        25.0            correct — 25 of 100
VARCHAR 's'      approx_unique 7               correct — s0..s6
Spark adapter    error         'Profiling is not available for this engine (Spark).'
```

Every value is independently correct, not merely present. The Spark path reports its
limitation explicitly rather than returning empty profiles — the plan called this out
because silently swallowing an unsupported case is the defect previously found in
`get_schema`.

### The approximation is labelled

```text
schema panel headers:
['Name', 'Type', 'Nullable', 'Position', 'Null %', 'Distinct (approx.)', 'Min', 'Max', 'Mean']
```

`approx_unique` is HyperLogLog, and the header says so. In a tool people use to check data,
presenting an estimate as an exact distinct count would be a correctness lie.

### Thread safety honoured

`_profile_workers` exists and `closeEvent` drains it alongside `_schema_workers`. This was a
hard requirement: a QThread alive at shutdown delivering posted events into freed memory was
a real SIGSEGV in this codebase.

### Settings

```text
profile_on_load    default True
profile_max_bytes  default 268,435,456 (256 MB)
```

As specified: on by default, bounded by a threshold, both exposed in Preferences.

## Negative controls — full suite, baseline 420

| mutation | result |
|---|---|
| flip `DEFAULT_PROFILE_ON_LOAD` to `False` | 1 failed, 419 passed |
| remove the `_profile_workers` drain from `closeEvent` | 1 failed, 419 passed |
| DuckDB `profile_dataset` returns empty profiles | 1 failed, 419 passed |

Each was verified as applied before running, and costs exactly one test.

## Environmental failure — a real bug found, not a false alarm

The first full run showed three failures: `test_installed_wheel_smoke`, `test_packaging`,
and `test_built_wheel_carries_the_real_commit`. All three are build-related; none touch
profiling. Root cause:

```text
Caused by: No space left on device (os error 28)
/dev/mapper/systemVG-LVRoot  28G  25G  2.6G  91% /
```

`scripts/smoke_installed_wheel.py:21` created its work directory with `tempfile.mkdtemp`
and **never removed it**. Each run leaves behind a full virtual environment — roughly
700 MB — and **212 had accumulated**, exhausting the disk until `uv build` failed.

This is worth dwelling on: the symptom was three red packaging tests on a branch that
touched neither packaging nor the build. Taken at face value it would have been reported as
"the profiling round broke the wheel build". It broke nothing; the disk was full.

Fixed in `93f75b3`: `try`/`finally` with `shutil.rmtree`, plus a test asserting no work
directory survives a run. Reverting the cleanup fails that guard. The
`Fresh virtual environment:` line is still printed — before cleanup — because the existing
test asserts on it to prove the smoke ran outside the project venv; removing it silently
broke that assertion on my first attempt.

212 leaked directories were removed; free space went from 2.6 GB to 4.4 GB.

## The boundary held

Version `0.5.2`, no tag, `main` untouched. `timid = true`, the `pyarrow` import, the
overwrite confirmation, `EngineKind` and the `DIALECT_MAPPING` identifiers all unchanged.
Schema inspection is unchanged and does not wait on profiling.

## Deferred

Exact distinct counts, histograms, value-frequency tables and Spark profiling remain out of
scope. How the nine profile columns read at narrow panel widths is a manual maintainer
check. Profiling has not been exercised against a source larger than `profile_max_bytes` on
real hardware — only the skip path is tested.

STATUS: APPROVED
