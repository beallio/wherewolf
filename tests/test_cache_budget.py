import os
import re
import subprocess
from pathlib import Path

SCRIPT = Path("scripts/check_cache_budget.sh")
BUDGET = 4 * 1024 * 1024 * 1024


def run_cache_budget(root: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["WHEREWOLF_CACHE_ROOT"] = str(root)
    return subprocess.run(
        [str(SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def test_cache_budget_rejects_a_non_symlink_root(tmp_path: Path) -> None:
    root = tmp_path / "wherewolf"
    root.mkdir()

    result = run_cache_budget(root)

    assert result.returncode != 0
    assert result.stderr.strip() == "cache root is not a symlink; it is back on the tmpfs"


def test_cache_budget_rejects_a_root_over_four_gibibytes(tmp_path: Path) -> None:
    target = tmp_path / "cache"
    target.mkdir()
    sparse_file = target / "sparse.bin"
    sparse_file.touch()
    with sparse_file.open("r+b") as file:
        file.truncate(BUDGET + 1)
    root = tmp_path / "wherewolf"
    root.symlink_to(target, target_is_directory=True)

    try:
        result = run_cache_budget(root)
    finally:
        sparse_file.unlink()

    assert result.returncode != 0
    assert result.stderr.strip() == f"cache budget exceeded: {BUDGET + 1} > {BUDGET}"


def test_cache_budget_reports_a_symlinked_root_within_budget(tmp_path: Path) -> None:
    target = tmp_path / "cache"
    target.mkdir()
    (target / "small.bin").write_bytes(b"cache")
    root = tmp_path / "wherewolf"
    root.symlink_to(target, target_is_directory=True)

    result = run_cache_budget(root)

    assert result.returncode == 0
    assert result.stderr == ""
    match = re.fullmatch(r"cache bytes: (\d+)\n", result.stdout)
    assert match is not None
    assert int(match.group(1)) > 0
