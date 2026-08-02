import re
from pathlib import Path

WORKFLOW = Path(".github/workflows/ci.yml")


def _job_block(workflow: str, job_name: str) -> str:
    pattern = rf"^  {re.escape(job_name)}:\n(?P<body>.*?)(?=^  [\w-]+:\n|\Z)"
    match = re.search(pattern, workflow, flags=re.MULTILINE | re.DOTALL)
    assert match, f"CI job {job_name!r} is missing"
    return match.group("body")


def _sync_lines(job: str) -> list[str]:
    lines = [line.strip() for line in job.splitlines() if "uv sync" in line]
    assert lines, "each CI job must explicitly install its dependencies"
    return lines


def _installs_spark(sync_lines: list[str]) -> bool:
    return any("--extra spark" in line or "--all-extras" in line for line in sync_lines)


def test_ci_install_contracts_match_the_tooling_each_leg_runs() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    jobs = {
        name: _job_block(workflow, name)
        for name in ("lint", "test-duckdb", "test-spark", "build", "qt-smoke")
    }

    # Do not restore --locked: the maintainer's relative exclude-newer-span makes the
    # lock impossible for CI to reproduce, even though the resolved dependencies are valid.
    assert all("--locked" not in line for job in jobs.values() for line in _sync_lines(job))

    lint_sync = _sync_lines(jobs["lint"])
    assert "ty check" in jobs["lint"]
    assert any("--dev" in line for line in lint_sync)
    assert _installs_spark(lint_sync), "ty resolves the optional Spark engine"

    duckdb_sync = _sync_lines(jobs["test-duckdb"])
    assert any("--dev" in line for line in duckdb_sync)
    assert not _installs_spark(duckdb_sync)
    assert "pytest -m spark" not in jobs["test-duckdb"]

    spark_sync = _sync_lines(jobs["test-spark"])
    assert any("--dev" in line for line in spark_sync)
    assert _installs_spark(spark_sync)
    assert "pytest -m spark" in jobs["test-spark"]

    build_sync = _sync_lines(jobs["build"])
    assert any("--dev" in line for line in build_sync)
    assert not _installs_spark(build_sync)
    assert "smoke_installed_wheel.py" in jobs["build"]

    qt_smoke_sync = _sync_lines(jobs["qt-smoke"])
    assert any("--dev" in line for line in qt_smoke_sync)
    assert not _installs_spark(qt_smoke_sync)
    assert "ubuntu-latest" in jobs["qt-smoke"]
    assert "macos-latest" in jobs["qt-smoke"]
    assert "windows-latest" in jobs["qt-smoke"]
    assert "tests/test_qt_stack.py" in jobs["qt-smoke"]
    assert "tests/test_desktop_duckdb_flow.py" in jobs["qt-smoke"]
    assert "./run.sh" not in jobs["qt-smoke"]
    assert "UV_PROJECT_ENVIRONMENT" in jobs["qt-smoke"]
    assert "UV_CACHE_DIR" in jobs["qt-smoke"]
    assert "XDG_CACHE_HOME" in jobs["qt-smoke"]
    assert "PYTHONPYCACHEPREFIX" in jobs["qt-smoke"]
    assert "TMPDIR" in jobs["qt-smoke"]
