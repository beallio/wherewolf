from pathlib import Path


def test_ci_has_separate_duckdb_only_and_opt_in_spark_tiers() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text()

    assert "test-duckdb:" in workflow
    assert "uv sync --locked --dev --python" in workflow
    assert "test-spark:" in workflow
    assert "uv sync --locked --extra spark --dev --python" in workflow
    assert "pytest -m spark" in workflow
    assert workflow.count("name: Verify interpreter") == 2
