# 验证证据

本文只记录当前净室仓库可复现的验证；旧仓库、旧分支或其他实现的结果不计入。

## 原创 ELF 夹具

夹具源码位于 `tests/fixtures/src/`，通过 `python scripts/build_fixtures.py` 交叉编译为 `x86_64-linux-gnu` 共享库。

| 文件 | 特征 | SHA-256 |
|---|---|---|
| `libsymbolic.so` | 符号与 DWARF 调试信息 | `f87e3005d28ad1751b90b088eaa6f3f73c788fe1f3f605cbc9a210726febdc96` |
| `libstripped.so` | `-O2 -s`，移除普通符号和调试信息 | `f7f4ef287303b0de81bb0e43723f8bf654d3261e9f1b4c5237f94bd71585c590` |
| `libcontrol_flow.so` | 运行态状态循环、循环回边与函数指针间接调用 | `51e50c32193c666dc2ace38935477cd88eea901ab77fc1dfdcd602647677888a` |

## Ghidra 版本矩阵

| Ghidra | 真实测试 | 结果 |
|---|---|---|
| 12.0.4 | 三个 `.so` 的导入、分析、内存/函数/反编译查询、事务写入和重开 | 通过 |
| 12.1.2 | 同一完整集成测试 | 通过 |

每个版本的命令：

```bash
mkdir -p /tmp/ghidra-mcp-java-home
GHIDRA_INSTALL_DIR=/absolute/path/to/ghidra \
  UV_CACHE_DIR=/tmp/ghidra-mcp-uv-cache \
  _JAVA_OPTIONS=-Duser.home=/tmp/ghidra-mcp-java-home \
  uv run pytest tests/integration/test_real_ghidra.py -q -s
```

测试是一个参数内循环，因此成功输出为 `1 passed`，但会逐一处理三个独立 `.so`。

## 容器验证

最终候选必须通过以下检查：

- `docker buildx build --platform linux/amd64 --no-cache --load` 成功。
- Ghidra 下载 SHA-256 校验成功，Python/JPype 都使用 CPython 3.12 ABI。
- 运行身份为 UID/GID 10001，非 root。
- `/health` 的 version、完整 Git commit、schema version 与当前构建一致。
- `/mcp` 缺 token 和错误 token 均返回 401，正确 token 能进入 MCP 协议处理。
- `tests/integration/test_container_mcp.py` 通过真实 MCP 完成分析、反编译、事务写入和重开。
- 写入容器停止后，新容器挂载同一卷仍能读取已保存的函数名。

容器集成测试：

```bash
GHIDRA_MCP_CONTAINER_URL=http://127.0.0.1:8765/mcp \
  GHIDRA_MCP_CONTAINER_TOKEN='<测试 token>' \
  GHIDRA_MCP_CONTAINER_RENAME_TO=container_verified_symbolic \
  uv run pytest tests/integration/test_container_mcp.py -q -s
```

跨容器重启后改为：

```bash
GHIDRA_MCP_CONTAINER_URL=http://127.0.0.1:8765/mcp \
  GHIDRA_MCP_CONTAINER_TOKEN='<测试 token>' \
  GHIDRA_MCP_CONTAINER_EXPECT_NAME=container_verified_symbolic \
  uv run pytest tests/integration/test_container_mcp.py -q -s
```

每次候选构建都应把镜像摘要与 `/health` 实测值记录在对应发布记录中；本文保留可重复执行的验收方法，不把某次本机镜像状态写成永久事实。
