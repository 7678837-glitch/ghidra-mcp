# Ghidra MCP

面向 headless 逆向分析的单进程 MCP 服务。Python 进程通过 PyGhidra 启动 JVM、管理持久化 Ghidra 项目，并向 AI 客户端暴露 34 个任务导向工具。

> 安全支持基线是 Ghidra 12.1.2+，不是所有历史版本。Streamable HTTP 必须配置 Bearer token；跨主机部署还必须在服务前终止 TLS。

## 使用 Docker 启动

从仓库根目录构建固定为 `linux/amd64` 的镜像：

```bash
docker buildx build \
  --platform linux/amd64 \
  --no-cache \
  --load \
  --build-arg GIT_COMMIT=<完整 Git commit> \
  -t ghidra-mcp:20260720.1 .
```

创建持久卷并仅监听本机回环地址：

```bash
docker volume create ghidra-mcp-projects
docker run --name ghidra-mcp \
  --platform linux/amd64 \
  -p 127.0.0.1:8765:8765 \
  -e GHIDRA_MCP_AUTH_TOKEN='<随机长 token>' \
  -v ghidra-mcp-projects:/data/projects \
  -v /absolute/path/to/binaries:/data/input:ro \
  ghidra-mcp:20260720.1
```

客户端连接 `http://127.0.0.1:8765/mcp`，并发送 `Authorization: Bearer <token>`。公开健康检查位于 `http://127.0.0.1:8765/health`。

## 本地 stdio 启动

前置条件：Python 3.11+、Ghidra 12.1.2+，以及可写的项目数据目录。

```bash
uv sync --locked
cp .env.example .env
GHIDRA_INSTALL_DIR=/absolute/path/to/ghidra \
  GHIDRA_MCP_TRANSPORT=stdio \
  uv run ghidra-mcp
```

stdio 模式用于同机 MCP 客户端，不要求 token。服务退出时会关闭仍由当前进程持有的程序会话。

## 配置

优先级固定为：环境变量 > `.env` > TOML > 默认值。默认 TOML 位于 `data/config/default.toml`。

| 环境变量 | 默认值 | 说明 |
|---|---:|---|
| `GHIDRA_INSTALL_DIR` | 无 | Ghidra 安装目录；必填 |
| `GHIDRA_MCP_TRANSPORT` | `stdio` | `stdio` 或 `streamable-http` |
| `GHIDRA_MCP_HOST` | `127.0.0.1` | HTTP 监听地址 |
| `GHIDRA_MCP_PORT` | `8765` | HTTP 监听端口，范围 1–65535 |
| `GHIDRA_MCP_STORAGE_ROOT` | `data/projects` | Ghidra 项目持久化目录 |
| `GHIDRA_MCP_INPUT_ROOT` | 无 | HTTP 模式必填；`program_open` 只能读取该目录内文件，符号链接也不能越界 |
| `GHIDRA_MCP_AUTH_TOKEN` | 无 | HTTP 模式必填；仅从环境变量或 `.env` 读取 |

未知 TOML 节或键会立即报错。不要把真实 token 写入 TOML、命令历史、日志或 Git。

## 文档

- [工具目录](docs/tools.md)：34 个默认工具及选择边界。
- [运维指南](docs/operations.md)：部署、健康检查、备份恢复与故障处理。
- [验证证据](docs/verification.md)：真实 `.so`、Ghidra 版本和可复现命令。
- [行为规格](docs/specification.md)：产品边界和硬性契约。
- [净室章程](CLEANROOM.md)：允许来源、禁止输入和发布边界。

## 开发验证

```bash
uv run pytest -m 'not integration' -q
uv run ruff check src tests scripts
python scripts/build_fixtures.py
GHIDRA_INSTALL_DIR=/absolute/path/to/ghidra \
  _JAVA_OPTIONS=-Duser.home=/tmp/ghidra-mcp-java-home \
  uv run pytest tests/integration/test_real_ghidra.py -q -s
```

容器端到端验证命令见 [验证证据](docs/verification.md)。
