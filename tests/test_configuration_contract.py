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
            "GHIDRA_MCP_INPUT_ROOT": str(tmp_path),
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


def test_streamable_http_requires_auth_token_and_input_root(tmp_path: Path) -> None:
    from ghidra_mcp.config import ConfigurationError, load_settings

    with pytest.raises(ConfigurationError, match="GHIDRA_MCP_AUTH_TOKEN"):
        load_settings(
            config_path=None,
            dotenv_path=None,
            environ={"GHIDRA_MCP_TRANSPORT": "streamable-http"},
        )

    with pytest.raises(ConfigurationError, match="GHIDRA_MCP_INPUT_ROOT"):
        load_settings(
            config_path=None,
            dotenv_path=None,
            environ={
                "GHIDRA_MCP_TRANSPORT": "streamable-http",
                "GHIDRA_MCP_AUTH_TOKEN": "test-token",
            },
        )


def test_auth_token_is_loaded_from_dotenv_but_never_exposed_by_repr(tmp_path: Path) -> None:
    from ghidra_mcp.config import load_settings

    dotenv = tmp_path / ".env"
    dotenv.write_text(
        f"GHIDRA_MCP_AUTH_TOKEN=private-test-token\nGHIDRA_MCP_INPUT_ROOT={tmp_path}\n",
        encoding="utf-8",
    )

    settings = load_settings(
        config_path=None,
        dotenv_path=dotenv,
        environ={"GHIDRA_MCP_TRANSPORT": "streamable-http"},
    )

    assert settings.auth_token == "private-test-token"
    assert settings.input_root == tmp_path.resolve()
    assert "private-test-token" not in repr(settings)


def test_input_root_uses_environment_dotenv_toml_precedence(tmp_path: Path) -> None:
    from ghidra_mcp.config import load_settings

    toml_root = tmp_path / "toml"
    dotenv_root = tmp_path / "dotenv"
    environment_root = tmp_path / "environment"
    config = tmp_path / "settings.toml"
    config.write_text(f'[storage]\ninput_root = "{toml_root}"\n', encoding="utf-8")
    dotenv = tmp_path / ".env"
    dotenv.write_text(f"GHIDRA_MCP_INPUT_ROOT={dotenv_root}\n", encoding="utf-8")

    settings = load_settings(
        config_path=config,
        dotenv_path=dotenv,
        environ={"GHIDRA_MCP_INPUT_ROOT": str(environment_root)},
    )

    assert settings.input_root == environment_root.resolve()
