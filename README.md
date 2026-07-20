# Ghidra MCP

面向自动化逆向分析的单进程 MCP 服务。服务通过 PyGhidra 加载 Ghidra，默认只暴露不超过 40 个任务导向工具，并允许显式启用按需工具组。

当前仓库采用净室工程流程：实现只依据本仓库的行为规格和公开官方 API，不继承任何既有项目的源码、测试或 Git 历史。

## 当前状态

正在进行阶段 0：净室边界、行为契约与 PyGhidra 可行性验证。当前版本不是发布候选。

## 目标基线

- Python 3.11+
- Ghidra 12.0+
- 本地集成使用 MCP stdio transport
- 远端服务使用 MCP Streamable HTTP
- 默认工具数不超过 40
- 配置优先级：环境变量 > `.env` > TOML > 默认值
