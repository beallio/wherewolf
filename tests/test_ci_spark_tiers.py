from pathlib import Path


def test_ci_has_separate_duckdb_only_and_opt_in_spark_tiers() -> None:
    """The two tiers must install differently: that is what proves each exit criterion.

    The DuckDB leg must NOT install the spark extra (a DuckDB-only install has no Spark
    requirement); the Spark leg must install it and opt in via the marker.
    """
    workflow = Path(".github/workflows/ci.yml").read_text()

    assert "test-duckdb:" in workflow
    assert "test-spark:" in workflow

    duckdb_leg = workflow.split("test-duckdb:", 1)[1].split("test-spark:", 1)[0]
    spark_leg = workflow.split("test-spark:", 1)[1]

    duckdb_sync = [ln for ln in duckdb_leg.splitlines() if "uv sync" in ln]
    spark_sync = [ln for ln in spark_leg.splitlines() if "uv sync" in ln]
    assert duckdb_sync and spark_sync

    # The DuckDB tier must not pull in Spark; the Spark tier must.
    assert all("--extra spark" not in ln for ln in duckdb_sync)
    assert any("--extra spark" in ln for ln in spark_sync)

    assert "pytest -m spark" in spark_leg
    assert "pytest -m spark" not in duckdb_leg
    assert workflow.count("name: Verify interpreter") == 2
