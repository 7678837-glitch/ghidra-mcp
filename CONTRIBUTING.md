# 贡献指南

感谢你改进 Ghidra MCP。提交改动前，请先阅读 [净室工程章程](CLEANROOM.md)；本项目只接受基于公开官方资料、可观察行为和仓库原创内容的贡献。

向本项目有意提交 Pull Request，即表示你有权提交该内容，并同意该贡献按照项目的 Apache License 2.0 授权；明确标注为“Not a Contribution”的沟通除外。

## 开始开发

前置条件：Python 3.11+、`uv`，生成 ELF 夹具所需的 Zig，以及运行集成测试时使用的 Ghidra 12.1.2+。

```bash
uv sync --locked --extra dev
uv run --locked pytest -m 'not integration' -q
uv run --locked ruff check src tests scripts
```

需要运行真实 Ghidra 测试时，先生成原创 ELF 夹具：

```bash
python scripts/build_fixtures.py
GHIDRA_INSTALL_DIR=/absolute/path/to/ghidra \
  _JAVA_OPTIONS=-Duser.home=/tmp/ghidra-mcp-java-home \
  uv run --locked pytest tests/integration/test_real_ghidra.py -q -s
```

容器端到端验证和版本矩阵见 [验证证据](docs/verification.md)。

## 变更要求

- Bug 修复先添加能复现问题的失败测试，再提交最小根因修复。
- 保持工具面向任务且边界清晰；不要增加同义 batch/bulk 工具或依赖 GUI 的能力。
- 新增或改变工具时，同步更新工具 schema 契约、`docs/tools.md` 和相关测试。
- 新增配置时保持环境变量 > `.env` > TOML > 默认值的优先级，并更新 `.env.example` 和 README。
- 不提交二进制样本、真实分析项目、凭据、私网地址、个人目录或生产部署信息。
- 只引用公开官方资料，并在 `docs/sources.md` 登记用于确认实现的来源。

## 提交前检查

```bash
uv run --locked pytest -m 'not integration' -q
uv run --locked ruff check src tests scripts
git diff --check
```

若改动影响 Ghidra API、持久化、容器或 HTTP 边界，还需运行对应的真实集成测试。请在 Pull Request 中列出实际执行的命令与结果；未运行的检查应明确说明。

安全漏洞不要通过公开 Issue 披露，按 [安全政策](SECURITY.md) 提交。
