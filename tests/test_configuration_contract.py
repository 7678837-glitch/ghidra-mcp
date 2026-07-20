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


def test_unimplemented_tool_groups_fail_instead_of_being_silently_ignored(tmp_path: Path) -> None:
    from ghidra_mcp.config import ConfigurationError, load_settings

    config = tmp_path / "settings.toml"
    config.write_text('[tools]\ngroups = ["advanced"]\n', encoding="utf-8")

    with pytest.raises(ConfigurationError, match=r"未知配置节 tools.*settings\.toml"):
        load_settings(config_path=config, dotenv_path=None, environ={})


def test_runtime_path_and_transport_are_validated_at_configuration_boundary(tmp_path: Path) -> None:
    from ghidra_mcp.config import ConfigurationError, load_settings

    install_dir = tmp_path / "ghidra"
    install_dir.mkdir()
    settings = load_settings(
        config_path=None,
        dotenv_path=None,
        environ={
            "GHIDRA_INSTALL_DIR": str(install_dir),
            "GHIDRA_MCP_TRANSPORT": "streamable-http",
            "GHIDRA_MCP_AUTH_TOKEN": "test-token",
        },
    )
    assert settings.install_dir == install_dir.resolve()
    assert settings.transport == "streamable-http"

    with pytest.raises(ConfigurationError, match="transport"):
        load_settings(
            config_path=None,
            dotenv_path=None,
            environ={"GHIDRA_MCP_TRANSPORT": "websocket"},
        )


def test_streamable_http_requires_non_empty_environment_auth_token() -> None:
    from ghidra_mcp.config import ConfigurationError, load_settings

    with pytest.raises(ConfigurationError, match="GHIDRA_MCP_AUTH_TOKEN"):
        load_settings(
            config_path=None,
            dotenv_path=None,
            environ={"GHIDRA_MCP_TRANSPORT": "streamable-http"},
        )


def test_auth_token_is_loaded_from_dotenv_but_never_exposed_by_repr(tmp_path: Path) -> None:
    from ghidra_mcp.config import load_settings

    dotenv = tmp_path / ".env"
    dotenv.write_text("GHIDRA_MCP_AUTH_TOKEN=private-test-token\n", encoding="utf-8")

    settings = load_settings(
        config_path=None,
        dotenv_path=dotenv,
        environ={"GHIDRA_MCP_TRANSPORT": "streamable-http"},
    )

    assert settings.auth_token == "private-test-token"
    assert "private-test-token" not in repr(settings)
