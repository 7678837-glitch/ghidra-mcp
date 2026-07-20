"""把本地工具注册表绑定到 FastMCP。"""

from __future__ import annotations

from hashlib import sha256
import hmac
from importlib.metadata import PackageNotFoundError, version as package_version
import inspect
import json
import os
from pathlib import Path
import subprocess

from mcp.server.fastmcp import FastMCP
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .registry import ToolRegistry


class StaticTokenVerifier(TokenVerifier):
    """验证部署者通过环境变量提供的单一 Bearer token。"""

    def __init__(self, expected_token: str) -> None:
        self._expected_token = expected_token

    async def verify_token(self, token: str) -> AccessToken | None:
        if not hmac.compare_digest(token, self._expected_token):
            return None
        return AccessToken(
            token=token,
            client_id="ghidra-mcp",
            scopes=["mcp"],
            subject="configured-client",
        )


def _schema_version(registry: ToolRegistry) -> str:
    contracts = [
        {
            "name": tool.name,
            "description": tool.description,
            "signature": str(inspect.signature(tool.handler)),
        }
        for tool in registry.enabled_tools()
    ]
    encoded = json.dumps(contracts, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return sha256(encoded).hexdigest()[:16]


def _runtime_version() -> str:
    for parent in Path(__file__).resolve().parents:
        version_file = parent / "VERSION"
        if version_file.is_file():
            return version_file.read_text(encoding="utf-8").strip()
    try:
        return package_version("ghidra-mcp")
    except PackageNotFoundError:
        return "unknown"


def _git_commit() -> str:
    configured = os.environ.get("GHIDRA_MCP_GIT_COMMIT", "").strip()
    if configured:
        return configured
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=Path(__file__).resolve().parent,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip() or "unknown"


def create_mcp_app(
    registry: ToolRegistry,
    *,
    host: str,
    port: int,
    auth_token: str | None = None,
    version: str | None = None,
    git_commit: str | None = None,
) -> FastMCP:
    auth = None
    verifier = None
    if auth_token is not None:
        base_url = f"http://{host}:{port}"
        auth = AuthSettings(
            issuer_url=base_url,
            resource_server_url=f"{base_url}/mcp",
            required_scopes=["mcp"],
        )
        verifier = StaticTokenVerifier(auth_token)
    app = FastMCP(
        "ghidra-mcp",
        host=host,
        port=port,
        auth=auth,
        token_verifier=verifier,
    )
    for tool in registry.enabled_tools():
        app.tool(name=tool.name, description=tool.description)(tool.handler)

    health_payload = {
        "status": "ok",
        "version": version or _runtime_version(),
        "git_commit": git_commit or _git_commit(),
        "schema_version": _schema_version(registry),
    }

    @app.custom_route("/health", methods=["GET"], include_in_schema=False)
    async def health(_request: Request) -> Response:
        return JSONResponse(health_payload)

    return app
