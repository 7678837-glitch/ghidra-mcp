# 变更记录

## 20260722.3

- 为 MCP 工具契约增加标准 `ToolAnnotations` 并纳入 schema 摘要。
- `program_close` 明确标记为会移除活跃会话的非幂等变更，同时保留“先保存、保存失败不关闭”的数据安全语义。
- 将开发测试依赖升级到 pytest 9.1.1，修复临时目录处理的中等级安全告警。

## 20260722.2

- `instructions_list` 明确返回请求起点、实际起点和跳过字节数，并支持严格起点校验。
- `function_get` 明确区分函数体内地址与未归属地址；新增 `function_body_add` 修正已确认的 detached continuation 范围。
- `references_list` 支持在显式对齐范围内伪反汇编未定义代码，补充 CFF 代码岛的 direct refs，并报告覆盖范围、来源和置信度。
- `control_flow_graph` 区分静态默认流与 Ghidra 分析器推断流，避免把 computed targets 表述为确定事实。
- 工具契约加入版本号并纳入 schema 摘要，使不兼容的响应结构变化可被客户端识别。

## 20260722.1

- 从空 Git 历史实现单进程 PyGhidra MCP 服务。
- 默认提供 34 个程序、导航、分析、检查与事务写工具。
- 支持本地 stdio 和带 Bearer 鉴权的 Streamable HTTP。
- 加入配置优先级、持久项目目录、健康元数据和 `linux/amd64` 非 root 镜像。
- 加入带符号、stripped、控制流复杂三类原创 ELF 夹具及真实 Ghidra 测试。
- 将安全最低版本设为 Ghidra 12.1.2，并在 JVM 启动前拒绝无法确认或低于基线的安装。
- 保存失败时使用 Ghidra 原生 undo 撤销已提交事务；批量关闭会继续处理全部会话。
- 根据历史实战对话将反编译默认输出限制为 50000 字符，并为 `memory_read` 增加可选解释视图。
- 从根 `VERSION` 生成 wheel 元数据，兼容 Ghidra `12.2` 这类两段版本号。
- 为自动分析增加 1–3600 秒可取消期限，并在超时或保存失败时回滚分析事务。
- HTTP 模式要求显式公开根 URL 与至少 32 字节 token，避免广告不可路由的监听地址。
