from __future__ import annotations

import ast
import tomllib
from pathlib import Path


def test_pyspark_is_an_optional_dependency_and_registry_uses_spec_lookup() -> None:
    config = tomllib.loads(Path("pyproject.toml").read_text())

    assert not any(
        dependency.startswith("pyspark") for dependency in config["project"]["dependencies"]
    )
    assert any(
        dependency.startswith("pyspark")
        for dependency in config["project"]["optional-dependencies"]["spark"]
    )

    registry = ast.parse(Path("src/wherewolf/execution/registry.py").read_text())
    assert 'find_spec("pyspark")' in Path("src/wherewolf/execution/registry.py").read_text()
    assert not any(
        isinstance(node, (ast.Import, ast.ImportFrom))
        and any(
            alias.name == "pyspark" or alias.name.startswith("pyspark.") for alias in node.names
        )
        for node in ast.walk(registry)
    )
