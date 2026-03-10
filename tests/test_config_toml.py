import toml
from pathlib import Path


def test_config_toml_is_valid():
    """Verify that .streamlit/config.toml exists and is valid TOML."""
    config_path = Path(".streamlit/config.toml")
    assert config_path.exists(), ".streamlit/config.toml does not exist"

    with open(config_path, "r") as f:
        config = toml.load(f)

    assert "browser" in config
    assert config["browser"].get("gatherUsageStats") is False
