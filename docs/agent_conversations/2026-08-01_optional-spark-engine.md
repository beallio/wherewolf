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

Implementation pending.
