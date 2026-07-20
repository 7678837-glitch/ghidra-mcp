from pathlib import Path

import pytest


def test_environment_overrides_dotenv_toml_and_defaults(tmp_path: Path) -> None:
    from ghidra_mcp.config import load_settings

    config = tmp_path / "settings.toml"
    config.write_text('[server]\ntransport = "stdio"\nport = 7000\n', encoding="utf-8")
    dotenv = tmp_path / ".env"
    dotenv.write_text("GHIDRA_MCP_PORT=7001\n", encoding="utf-8")

    settings = load_settings(
        config_path=config,
        dotenv_path=dotenv,
        environ={"GHIDRA_MCP_PORT": "7002"},
    )

    assert settings.port == 7002


def test_unknown_toml_key_reports_key_and_source(tmp_path: Path) -> None:
    from ghidra_mcp.config import ConfigurationError, load_settings

    config = tmp_path / "settings.toml"
    config.write_text('[server]\nporrt = 7000\n', encoding="utf-8")

    with pytest.raises(ConfigurationError, match=r"server\.porrt.*settings\.toml"):
        load_settings(config_path=config, dotenv_path=None, environ={})
