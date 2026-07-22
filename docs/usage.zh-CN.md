# 使用指南

[English](usage.md)

本文独立说明安装、MCP 客户端连接、正常分析生命周期、持久化和容器镜像可用性。

## 选择传输方式

- MCP 客户端与 Ghidra 位于同一可信机器时使用 `stdio`。客户端负责拉起并持有服务进程，不需要 token。
- 远程或容器访问使用 `streamable-http`。必须配置输入根目录、客户端可见的公开根 URL，以及至少 32 个 UTF-8 字节的 Bearer token。非回环访问必须在可信反向代理终止 TLS。

## 使用公开容器

GHCR package 设为 public 后：

```bash
docker pull ghcr.io/xjoker/ghidra-mcp:latest
docker volume create ghidra-mcp-projects
(
read -rsp 'Ghidra MCP token: ' GHIDRA_MCP_AUTH_TOKEN && echo
export GHIDRA_MCP_AUTH_TOKEN
docker run -d --name ghidra-mcp \
  --platform linux/amd64 \
  -p 127.0.0.1:8765:8765 \
  -e GHIDRA_MCP_PUBLIC_URL=http://127.0.0.1:8765 \
  -e GHIDRA_MCP_AUTH_TOKEN \
  -v ghidra-mcp-projects:/data/projects \
  -v /absolute/path/to/binaries:/data/input:ro \
  ghcr.io/xjoker/ghidra-mcp:latest
)
```

隐藏输入可避免 token 值进入 shell history。拥有 Docker daemon 权限的用户仍可查看容器环境变量，因此必须限制 daemon 访问。

可复现部署应使用 `20260722.5` 这类版本标签；只有接受自动升级时才使用 `latest`。验证功能前先读取部署后的 `/health`：

```bash
curl -fsS http://127.0.0.1:8765/health
```

期望包含 `status`、`version`、`git_commit` 和 `schema_version`。进程健康不代表能成功导入二进制，还应实际调用一次 `program_open`。

## 从源码运行 stdio

```bash
git clone https://github.com/xjoker/ghidra-mcp.git
cd ghidra-mcp
uv sync --locked
cp .env.example .env
```

把 `GHIDRA_INSTALL_DIR` 指向 Ghidra 12.1.2+，再让 MCP 客户端拉起：

```text
uv --directory /absolute/path/to/ghidra-mcp run ghidra-mcp
```

客户端环境设置 `GHIDRA_INSTALL_DIR=/absolute/path/to/ghidra` 和 `GHIDRA_MCP_TRANSPORT=stdio`。

## 分析生命周期

正常工具顺序如下：

1. 使用二进制路径调用 `program_open`。HTTP 模式只接受 `GHIDRA_MCP_INPUT_ROOT` 内的常规文件。
2. 保存返回的 `program_id`，后续工具复用它，不要重复打开二进制。
3. 使用 `program_info`、`functions_list`、`instructions_list`、`references_list` 和 `decompile_function` 探索。
4. 仅在确有意图时使用写工具。写入位于 Ghidra 事务中，并持久化到项目目录。
5. 完成后调用 `program_close`。它先保存；保存失败时保持会话打开。

地址使用 Ghidra 字符串格式。Ghidra 跳过未定义字节时，`instructions_list` 会同时报告请求起点和实际起点。Detached continuation 在使用 `function_body_add` 明确加入前不属于函数体。

## 持久化与备份

`GHIDRA_MCP_STORAGE_ROOT` 保存持久化 Ghidra 项目。容器中应把 `/data/projects` 挂载为独立卷，把 `/data/input` 只读挂载。升级时绝不能覆盖唯一项目卷。

备份前停止写入并归档项目卷。恢复到新卷后，用独立容器验证函数名、注释等已保存数据，再切换流量。完整步骤见 [operations.md](operations.md)。

## 镜像发布状态

`.github/workflows/publish-container.yml` 在 `main` push 后使用仓库 `GITHUB_TOKEN` 发布，生成版本标签、`latest`、SBOM 和 provenance，并回拉远端 digest 验证。

GitHub Container Registry 的 package 可见性与 workflow 成功相互独立。首次发布后，所有者必须把 package 设为 public。只有未执行 `docker login` 时下面命令成功，才能认定公开可下载：

```bash
docker pull ghcr.io/xjoker/ghidra-mcp:<VERSION>
```

## 故障处理

- `/mcp` 返回 `401`：Bearer token 缺失或错误。
- 公开 URL 报错：填写客户端看到的 HTTP(S) 根 URL，不要使用 `0.0.0.0` 或 `::`。
- 输入路径被拒绝：文件必须位于 `GHIDRA_MCP_INPUT_ROOT` 内，符号链接不能越界。
- 项目锁错误：另一个进程仍持有项目；先关闭程序或正常停止持有者。
- health commit 不匹配：运行容器仍是旧版本；停止功能验证，先更新镜像和容器。

HTTP 暴露到本机以外前，请阅读 [SECURITY.md](../SECURITY.md)。
