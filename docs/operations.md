# 运维指南

## 部署前检查

1. 读取根目录 `VERSION`，并把完整 Git commit 传给 Docker build arg。
2. 使用 `--platform linux/amd64 --no-cache` 构建，确认 Ghidra SHA-256 校验成功。
3. 生成随机长 token，通过环境变量或未入库 `.env` 提供。
4. 把输入目录只读挂载到 `/data/input`，把命名卷挂载到 `/data/projects`。
5. 非本机访问必须在反向代理终止 TLS，并限制可信来源；应用自身只提供 HTTP。

## 启动与健康检查

```bash
docker run -d --name ghidra-mcp \
  --platform linux/amd64 \
  -p 127.0.0.1:8765:8765 \
  -e GHIDRA_MCP_AUTH_TOKEN='<随机长 token>' \
  -v ghidra-mcp-projects:/data/projects \
  -v /absolute/path/to/binaries:/data/input:ro \
  ghidra-mcp:20260720.1
curl -fsS http://127.0.0.1:8765/health
```

期望 JSON 字段：

```json
{
  "status": "ok",
  "version": "20260720.1",
  "git_commit": "<完整 Git commit>",
  "schema_version": "<16 位十六进制摘要>"
}
```

`status=ok` 只表示 MCP 进程已启动。是否能导入实际二进制，必须通过一次带鉴权的 `program_open` 验证。

## 备份和恢复项目卷

先停止写入容器，避免复制到一半的项目状态。下面命令把卷内容归档到当前目录：

```bash
docker run --rm \
  -v ghidra-mcp-projects:/source:ro \
  -v "$PWD":/backup \
  ubuntu:24.04@sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90 \
  tar -C /source -czf /backup/ghidra-mcp-projects.tar.gz .
```

恢复到新卷，保留原卷作为回滚点：

```bash
docker volume create ghidra-mcp-projects-restored
docker run --rm \
  -v ghidra-mcp-projects-restored:/target \
  -v "$PWD":/backup:ro \
  ubuntu:24.04@sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90 \
  tar -C /target -xzf /backup/ghidra-mcp-projects.tar.gz
```

用恢复卷启动新容器并执行真实 `program_open`；确认函数名、注释等事务写入仍存在后再切换流量。不要原地覆盖唯一数据卷。

## 常见故障

| 现象 | 原因与处理 |
|---|---|
| HTTP 启动时报 token 缺失 | 设置非空 `GHIDRA_MCP_AUTH_TOKEN`；stdio 不需要 |
| `/mcp` 返回 401 | 缺少或错误的 `Authorization: Bearer <token>` |
| `/mcp` 返回 400 | token 已通过，但请求不是有效 MCP 消息 |
| `Unable to lock project` | 另一个会话/进程仍持有同一项目；先调用 `program_close` 或正常停止持有者 |
| Ghidra 安装目录不存在 | 核对 `GHIDRA_INSTALL_DIR`；容器固定为 `/opt/ghidra` |
| health commit 与预期不符 | 镜像或容器未更新；停止验证功能，重新以正确 context 和 commit 构建 |

## 安全边界

- Bearer token 是单一部署凭据，没有用户级权限模型；泄露后立即轮换并重启容器。
- 输入文件会由 Ghidra 解析，应把服务放在受限容器和最小网络权限下。
- 服务日志仅写 stdout/stderr，不应记录 token、二进制内容或个人信息。
- 不要把 Docker socket、宿主根目录或可执行敏感目录挂入容器。
