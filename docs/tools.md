# 默认工具目录

默认 catalog 只有 34 个工具。典型流程是 `program_open` → 查询/分析工具 → 事务写工具 → `program_close`。地址接受 Ghidra 可解析的地址文本；所有需要 `program_id` 的工具只操作当前进程已打开的会话。

## 程序与内存

| 工具 | 用途 | 选择边界 |
|---|---|---|
| `program_open` | 导入或重开二进制，可选择自动分析 | 每个成功调用都必须最终配对 `program_close` |
| `program_list` | 列出当前进程持有的程序会话 | 只反映当前进程，不是磁盘项目清单 |
| `program_info` | 返回格式、语言、编译器和地址范围 | 不返回函数或符号详情 |
| `program_close` | 保存并释放程序上下文和项目锁 | 完成分析后必须调用 |
| `memory_blocks_list` | 列出内存块、范围和权限 | 先用它定位可读范围 |
| `memory_read` | 读取最多 1 MiB 的原始字节 | 已知地址时使用 |
| `memory_search` | 搜索精确十六进制字节模式 | 文本语义搜索改用 `strings_list` |

## 导航与列表

| 工具 | 用途 | 选择边界 |
|---|---|---|
| `functions_list` | 分页列出函数 | 查单个地址详情用 `function_get` |
| `function_get` | 返回包含地址的函数详情 | 地址不在函数中会快速失败 |
| `instructions_list` | 分页读取指令 | 中间表示用 `pcode_list` |
| `symbols_list` | 分页列出并按名称片段过滤符号 | 改名用 `symbol_rename` |
| `references_list` | 查询地址的入向、出向或双向引用 | 函数级调用关系用 `call_graph` |
| `strings_list` | 分页列出已定义字符串 | 未定义原始字节用 `memory_search` |
| `data_list` | 分页列出已定义数据 | 单个地址详情用 `data_get` |
| `data_get` | 返回包含地址的已定义数据 | 不创建或修改数据 |
| `comments_list` | 分页列出标准注释 | 写入或删除用 `comment_set` |
| `variables_list` | 列出函数参数和局部变量 | 输入函数内地址 |
| `data_types_list` | 分页列出数据类型 | 完整定义用 `data_type_get` |
| `data_type_get` | 按完整路径读取数据类型 | 应用到内存用 `data_type_apply` |
| `function_tags` | 列出函数标签 | 修改用 `function_tag_update` |
| `bookmarks_list` | 分页列出书签 | 修改用 `bookmark_set` |

## 分析图与中间表示

| 工具 | 用途 | 选择边界 |
|---|---|---|
| `decompile_function` | 反编译包含地址的函数 | 需要显式指令时用 `instructions_list` |
| `call_graph` | 返回一跳调用者和被调用者 | 不递归展开整图 |
| `control_flow_graph` | 返回函数内指令级控制流边 | 跨函数关系用 `call_graph` |
| `pcode_list` | 返回函数指令对应 P-code | 适合检查底层语义 |
| `analysis_run` | 对已打开程序同步运行自动分析 | 首次打开通常直接设置 `analyze=true` |

## 事务写入

| 工具 | 用途 | 选择边界 |
|---|---|---|
| `function_rename` | 重命名包含地址的函数 | 非函数主符号用 `symbol_rename` |
| `symbol_rename` | 重命名指定地址的主符号 | 函数语义名优先用 `function_rename` |
| `comment_set` | 设置或删除 eol/pre/post/plate/repeatable 注释 | `text=null` 表示删除 |
| `function_create` | 在确认的入口创建函数 | 已有函数时用 `function_rename` |
| `function_delete` | 删除入口地址精确匹配的函数 | 不接受函数内部地址 |
| `data_type_apply` | 在地址创建已有类型的数据定义 | 冲突不会被静默清除 |
| `function_tag_update` | 精确添加或移除函数标签 | 查询用 `function_tags` |
| `bookmark_set` | 设置或删除书签 | `comment=null` 表示删除匹配书签 |

所有写工具使用单个 Ghidra 事务；异常时回滚。工具不会评价名称或注释“是否足够好”，也不会用子串猜测目标。
