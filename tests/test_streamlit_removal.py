"""Regression guard for the retired Streamlit runtime."""

from pathlib import Path


def test_runtime_and_ci_inputs_contain_no_streamlit_residue() -> None:
    """No supported source, test, dependency, or CI path may revive Streamlit."""
    roots = (Path("src"), Path("tests"), Path("pyproject.toml"), Path(".github"))
    matches: list[Path] = []
    for root in roots:
        paths = root.rglob("*") if root.is_dir() else (root,)
        for path in paths:
            if (
                path.is_file()
                and path.suffix in {".py", ".toml", ".yml", ".yaml"}
                and path.resolve() != Path(__file__).resolve()
                and "streamlit" in path.read_text(encoding="utf-8").lower()
            ):
                matches.append(path)
    assert matches == []
