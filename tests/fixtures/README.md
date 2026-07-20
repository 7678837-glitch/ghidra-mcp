# ELF 共享库夹具

这些夹具完全由本仓库源码生成，不包含第三方二进制：

- `libsymbolic.so`：保留符号与 DWARF 调试信息。
- `libstripped.so`：优化并移除普通符号和调试信息，仅保留导出符号。
- `libcontrol_flow.so`：用运行态状态循环和函数指针分派制造控制流平坦化风格的间接控制流。

构建：

```bash
python scripts/build_fixtures.py
```

2026-07-20 使用 Zig 0.16.0 构建的 SHA-256：

```text
f87e3005d28ad1751b90b088eaa6f3f73c788fe1f3f605cbc9a210726febdc96  libsymbolic.so
f7f4ef287303b0de81bb0e43723f8bf654d3261e9f1b4c5237f94bd71585c590  libstripped.so
51e50c32193c666dc2ace38935477cd88eea901ab77fc1dfdcd602647677888a  libcontrol_flow.so
```

真实 Ghidra 测试：

```bash
mkdir -p /tmp/ghidra-mcp-java-home
GHIDRA_INSTALL_DIR=/path/to/ghidra \
  _JAVA_OPTIONS=-Duser.home=/tmp/ghidra-mcp-java-home \
  python -m pytest tests/integration/test_real_ghidra.py -q -s
```

`user.home` 指向任务临时目录，防止测试修改用户的 Ghidra 配置。
