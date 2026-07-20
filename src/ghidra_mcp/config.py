"""服务配置加载与边界校验。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
import os
import tomllib


class ConfigurationError(ValueError):
    """配置文件或环境变量不符合公开契约。"""


@dataclass(frozen=True, slots=True)
class Settings:
    transport: str = "stdio"
    host: str = "127.0.0.1"
    port: int = 8765
    tool_groups: tuple[str, ...] = ()
    storage_root: Path = Path("data/projects")


_ALLOWED_KEYS = {
    "server": {"transport", "host", "port"},
    "tools": {"groups"},
    "storage": {"root"},
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
    tools = document.get("tools", {})
    storage = document.get("storage", {})
    assert isinstance(server, dict) and isinstance(tools, dict) and isinstance(storage, dict)

    def value(env_key: str, toml_values: dict[str, object], toml_key: str, default: object) -> object:
        return environment.get(env_key, dotenv.get(env_key, toml_values.get(toml_key, default)))

    groups_value = value("GHIDRA_MCP_TOOL_GROUPS", tools, "groups", ())
    if isinstance(groups_value, str):
        groups = tuple(item.strip() for item in groups_value.split(",") if item.strip())
    elif isinstance(groups_value, list):
        groups = tuple(str(item) for item in groups_value)
    else:
        groups = tuple(groups_value)

    return Settings(
        transport=str(value("GHIDRA_MCP_TRANSPORT", server, "transport", "stdio")),
        host=str(value("GHIDRA_MCP_HOST", server, "host", "127.0.0.1")),
        port=_integer(value("GHIDRA_MCP_PORT", server, "port", 8765), key="server.port"),
        tool_groups=groups,
        storage_root=Path(str(value("GHIDRA_MCP_STORAGE_ROOT", storage, "root", "data/projects"))),
    )
