"""服务配置加载与边界校验。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping
import os
import tomllib


class ConfigurationError(ValueError):
    """配置文件或环境变量不符合公开契约。"""


@dataclass(frozen=True, slots=True)
class Settings:
    install_dir: Path | None = None
    transport: str = "stdio"
    host: str = "127.0.0.1"
    port: int = 8765
    storage_root: Path = Path("data/projects")
    input_root: Path | None = None
    auth_token: str | None = field(default=None, repr=False)


_ALLOWED_KEYS = {
    "ghidra": {"install_dir"},
    "server": {"transport", "host", "port"},
    "storage": {"root", "input_root"},
}


def _read_toml(path: Path | None) -> dict[str, object]:
    if path is None or not path.exists():
        return {}
    with path.open("rb") as stream:
        document = tomllib.load(stream)
    for section, values in document.items():
        if section not in _ALLOWED_KEYS:
            raise ConfigurationError(f"未知配置节 {section}，来源 {path.name}")
        if not isinstance(values, dict):
            raise ConfigurationError(f"配置节 {section} 必须是表，来源 {path.name}")
        for key in values:
            if key not in _ALLOWED_KEYS[section]:
                raise ConfigurationError(f"未知配置键 {section}.{key}，来源 {path.name}")
    return document


def _read_dotenv(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not key.strip():
            raise ConfigurationError(f"无效 .env 行 {line_number}，来源 {path.name}")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _integer(value: object, *, key: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ConfigurationError(f"{key} 必须是整数，实际为 {value!r}") from error


def load_settings(
    *,
    config_path: Path | None = Path("data/config/default.toml"),
    dotenv_path: Path | None = Path(".env"),
    environ: Mapping[str, str] | None = None,
) -> Settings:
    """按环境变量、.env、TOML、默认值的顺序合并配置。"""

    document = _read_toml(config_path)
    dotenv = _read_dotenv(dotenv_path)
    environment = os.environ if environ is None else environ

    server = document.get("server", {})
    ghidra = document.get("ghidra", {})
    storage = document.get("storage", {})
    assert (
        isinstance(server, dict)
        and isinstance(ghidra, dict)
        and isinstance(storage, dict)
    )

    def value(env_key: str, toml_values: dict[str, object], toml_key: str, default: object) -> object:
        return environment.get(env_key, dotenv.get(env_key, toml_values.get(toml_key, default)))

    transport = str(value("GHIDRA_MCP_TRANSPORT", server, "transport", "stdio"))
    if transport not in {"stdio", "streamable-http"}:
        raise ConfigurationError("server.transport 必须是 stdio 或 streamable-http")
    auth_token = environment.get("GHIDRA_MCP_AUTH_TOKEN", dotenv.get("GHIDRA_MCP_AUTH_TOKEN", ""))
    auth_token = auth_token.strip() or None
    if transport == "streamable-http" and auth_token is None:
        raise ConfigurationError("streamable-http 必须设置 GHIDRA_MCP_AUTH_TOKEN")
    input_value = value("GHIDRA_MCP_INPUT_ROOT", storage, "input_root", "")
    input_root = Path(str(input_value)).resolve() if input_value else None
    if transport == "streamable-http" and input_root is None:
        raise ConfigurationError("streamable-http 必须设置 GHIDRA_MCP_INPUT_ROOT")
    install_value = value("GHIDRA_INSTALL_DIR", ghidra, "install_dir", "")
    install_dir = Path(str(install_value)).resolve() if install_value else None
    port = _integer(value("GHIDRA_MCP_PORT", server, "port", 8765), key="server.port")
    if not 1 <= port <= 65535:
        raise ConfigurationError("server.port 必须在 1 到 65535 之间")

    return Settings(
        install_dir=install_dir,
        transport=transport,
        host=str(value("GHIDRA_MCP_HOST", server, "host", "127.0.0.1")),
        port=port,
        storage_root=Path(str(value("GHIDRA_MCP_STORAGE_ROOT", storage, "root", "data/projects"))),
        input_root=input_root,
        auth_token=auth_token,
    )
