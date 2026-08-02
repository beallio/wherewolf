# Optional Spark engine implementation session

Date: 2026-08-01

## Objective

Implement Phase 13 so PySpark is an opt-in extra while preserving a tested,
memory-bounded Spark integration tier.

## Starting point

- Base and plan commit: `e4ae860bb1b1e9e93d8a5c1429ff0c21d00a29ce`
  (`docs(plans): scope phase 13 optional spark engine`). The implementation
  branch starts at this commit, so the existing plan is its first commit.
- Python 3.14 default suite: `352 passed, 1 skipped, 1 warning in 22.85s`.
- Python 3.12 default suite: `352 passed, 1 skipped, 1 warning in 14.52s`.
- The warning in both runs came from a real PySpark Excel test. This confirms
  the default tier currently starts Spark and must be made opt-out.
- Java detected locally: OpenJDK 25.0.4. The planned Spark verification is
  limited to this Linux machine and this JDK; it is not cross-platform or
  multi-JDK verification.

## Historical-constraint lookup

The required `memory_researcher` lookup found no usable agent-memory records:
the index was unavailable. No memory claim IDs are therefore recorded. Current
repository evidence was used instead: `EngineRegistry` is the one lazy
`find_spec("pyspark")` discovery path; Spark requests need request-specific
job groups; and the protected Streamlit paths must remain unchanged.

## Measurement decision rules

- Record command output and exact pytest tallies, not qualitative status.
- Use a single session-scoped Spark fixture with `SPARK_LOCAL_DIRS` under
  `/tmp/wherewolf`, `local[1]`, a 512 MiB driver, UI disabled, and one shuffle
  partition. This bounds JVM use on the approximately 2.9 GiB-RAM host with a
  nearly-full 3 GiB tmpfs.
- Peak Spark memory is recorded as `not measured` unless a direct measurement
  is obtained; it will not be estimated.

## Results

### Task 2 — opt-in, memory-bounded Spark test tier

- Added the `spark` pytest marker and default `-m 'not spark'` selection.
- The one session-scoped fixture stores Spark local work in
  `/tmp/wherewolf/spark-local`, which resolves through the cache symlink to
  `/home/beallio/.local/state/wherewolf-cache`, rather than bare `/tmp`.
- Fixture settings: `local[1]`, `spark.driver.memory=512m`, disabled Spark UI,
  and one shuffle partition. These serialize local execution, explicitly cap
  the driver, avoid the UI process, and avoid the default 200 shuffle tasks.
- Focused default-tier proof: `2 passed, 2 deselected in 0.09s` for the tier
  configuration and Spark-engine module tests.
- Focused Spark-tier proof: `2 passed, 1 deselected, 1 warning in 5.52s` for
  the real schema and fixture-configuration tests.

### Review round 01 — Tasks 5–13

The committed review at `681b4a0` found the first four tasks complete and
required the remaining work. Its own V3 counterfactual measurement proved that
the default tier starts no JVM (`353 passed, 5 deselected`); it was therefore
not rerun in this round.

#### Revalidated cancellation evidence

The requested `memory_researcher` lookup could not return indexed claims while
the memory index was synchronizing. Repository history was used instead:
DuckDB adapters are request-scoped, handles carry the request UUID, and an
interrupt must affect only that request. Spark now mirrors that contract with a
request-derived job group. No agent-memory claim IDs are available.

#### Decisions

- The desktop shell now has an engine selector. Spark is visible but disabled
  with `wherewolf[spark]` and Java installation guidance when unavailable.
- A Spark engine creates no session in its constructor. Its first request uses
  `SparkSession.builder.getOrCreate()` with `local[1]`, 512 MiB driver memory,
  disabled UI, and one shuffle partition, then takes a child SQL session. This
  reuses the one JVM-backed context while isolating temporary views per
  request.
- Schema lookup now propagates engine errors to the registry, which returns a
  `SchemaResult` with `error_type` and `error_message`; an actual zero-column
  frame remains a success with no error.
- Each execution calls `setJobGroup` with its request UUID. Cancellation calls
  `cancelJobGroup` only for that UUID; `cancelAllJobs` is absent.
- All request temporary views are dropped in `finally`, including failures and
  cancellation. Spark full export is deliberately unsupported, so it creates
  no export temporary directory to clean up.
- `.json` means a JSON array and `.jsonl` means one JSON object per line. A
  suffix/content mismatch raises an actionable error instead of silently
  returning a wrong frame.
- CI is split into a DuckDB-only matrix (`uv sync --dev`) and an explicit
  Spark+Java matrix (`uv sync --extra spark --dev`, `pytest -m spark`). The
  interpreter verification step remains in both legs.

#### Measured results

- Final default tier: `364 passed, 7 deselected in 15.44s` on Python 3.14 and
  `363 passed, 7 deselected in 5.85s` on Python 3.12 (both without a JVM).
- Final Spark tier: `7 passed, 364 deselected, 1 warning in 9.49s` on Python
  3.14. Peak memory: not measured in this round. `/tmp` change: not measured
  in this round.
- The Spark tier uses tiny inputs only. No performance or scale testing was
  performed. Verification is limited to Linux and the local JDK; macOS,
  Windows, other JDKs, and cluster/remote Spark remain unverified.

#### V8 mutation checks

Each mutation was applied to committed `2b0b92e`, its named test failed, and
the source was restored before the next mutation.

1. Eager `import pyspark` failed
   `tests/test_spark_dependency.py::test_spark_engine_has_no_eager_pyspark_import`.
2. `cancelAllJobs` in place of request cancellation failed
   `tests/test_spark_engine.py::test_spark_engine_cancels_only_its_request_job_group`.
3. Swallowing the schema error failed
   `tests/test_registry.py::test_spark_schema_failure_is_distinguishable_from_an_empty_schema`.
4. Omitting request temporary-view cleanup failed both parameter cases of
   `tests/test_spark_engine.py::test_spark_engine_drops_request_temp_views_after_a_failed_or_cancelled_query`.
5. Removing `-m 'not spark'` failed
   `tests/test_spark_test_tier.py::test_spark_tests_are_opt_in`. This is the
   configuration guard for V3; the review's JVM-start counterfactual was
   already measured and was not rerun, as requested.
6. Reading a JSON array as JSON Lines failed
   `tests/test_spark_engine.py::test_spark_engine_reads_json_array_and_json_lines`
   with a row count of 8 instead of 2.
