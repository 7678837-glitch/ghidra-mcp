#!/usr/bin/env bash
# 幂等的 Cloud Agent 开发环境安装脚本。
# 目标：让 `uv run ghidra-mcp` 与集成测试可直接运行。
set -euo pipefail

UV_VERSION="0.8.0"
GHIDRA_URL="https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_12.1.2_build/ghidra_12.1.2_PUBLIC_20260605.zip"
GHIDRA_SHA256="b62e81a0390618466c019c60d8c2f796ced2509c4c1aea4a37644a77272cf99d"
GHIDRA_INSTALL_DIR="${GHIDRA_INSTALL_DIR:-/opt/ghidra}"
ZIG_VERSION="0.16.0"
ZIG_URL="https://ziglang.org/download/${ZIG_VERSION}/zig-x86_64-linux-${ZIG_VERSION}.tar.xz"
ZIG_SHA256="70e49664a74374b48b51e6f3fdfbf437f6395d42509050588bd49abe52ba3d00"
ZIG_INSTALL_DIR="${ZIG_INSTALL_DIR:-/opt/zig}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

log() { printf '[install] %s\n' "$*"; }

require_java() {
  if ! command -v java >/dev/null 2>&1; then
    echo "[install] 致命错误：未找到 java。Ghidra 需要 JDK/JRE 21+。" >&2
    exit 1
  fi
  log "java: $(java -version 2>&1 | head -n1)"
}

install_uv() {
  if command -v uv >/dev/null 2>&1; then
    log "uv 已存在: $(uv --version)"
    return
  fi
  log "安装 uv ${UV_VERSION}"
  curl -LsSf "https://astral.sh/uv/${UV_VERSION}/install.sh" | sh
  export PATH="$HOME/.local/bin:$PATH"
  command -v uv >/dev/null 2>&1 || { echo "[install] 致命错误：uv 安装后仍不可用" >&2; exit 1; }
  log "uv: $(uv --version)"
}

install_ghidra() {
  if [ -x "${GHIDRA_INSTALL_DIR}/ghidraRun" ]; then
    log "Ghidra 已存在于 ${GHIDRA_INSTALL_DIR}"
    return
  fi
  log "下载并安装 Ghidra 到 ${GHIDRA_INSTALL_DIR}"
  local tmp_zip extract_dir
  tmp_zip="$(mktemp /tmp/ghidra.XXXXXX.zip)"
  extract_dir="$(mktemp -d /tmp/ghidra-extract.XXXXXX)"
  curl -fsSL --continue-at - --retry 5 --retry-all-errors --retry-max-time 600 \
    "$GHIDRA_URL" -o "$tmp_zip"
  echo "${GHIDRA_SHA256}  ${tmp_zip}" | sha256sum -c -
  unzip -q "$tmp_zip" -d "$extract_dir"
  local sudo_cmd=""
  if [ ! -w "$(dirname "$GHIDRA_INSTALL_DIR")" ]; then
    sudo_cmd="sudo"
  fi
  $sudo_cmd rm -rf "$GHIDRA_INSTALL_DIR"
  $sudo_cmd mv "$extract_dir"/ghidra_*_PUBLIC "$GHIDRA_INSTALL_DIR"
  rm -rf "$tmp_zip" "$extract_dir"
  [ -x "${GHIDRA_INSTALL_DIR}/ghidraRun" ] || { echo "[install] 致命错误：Ghidra 安装校验失败" >&2; exit 1; }
  log "Ghidra 安装完成"
}

install_zig() {
  # Zig 用于生成可复现的 ELF 测试夹具（见 CONTRIBUTING.md）。
  if command -v zig >/dev/null 2>&1; then
    log "zig 已存在: $(zig version)"
    return
  fi
  if [ -x "${ZIG_INSTALL_DIR}/zig" ]; then
    log "zig 已存在于 ${ZIG_INSTALL_DIR}"
    return
  fi
  log "下载并安装 Zig ${ZIG_VERSION} 到 ${ZIG_INSTALL_DIR}"
  local tmp_tar extract_dir sudo_cmd=""
  tmp_tar="$(mktemp /tmp/zig.XXXXXX.tar.xz)"
  extract_dir="$(mktemp -d /tmp/zig-extract.XXXXXX)"
  curl -fsSL --retry 5 --retry-all-errors --retry-max-time 300 "$ZIG_URL" -o "$tmp_tar"
  echo "${ZIG_SHA256}  ${tmp_tar}" | sha256sum -c -
  tar -xJf "$tmp_tar" -C "$extract_dir"
  [ -w "$(dirname "$ZIG_INSTALL_DIR")" ] || sudo_cmd="sudo"
  $sudo_cmd rm -rf "$ZIG_INSTALL_DIR"
  $sudo_cmd mv "$extract_dir"/zig-* "$ZIG_INSTALL_DIR"
  rm -rf "$tmp_tar" "$extract_dir"
  $sudo_cmd ln -sf "${ZIG_INSTALL_DIR}/zig" /usr/local/bin/zig
  command -v zig >/dev/null 2>&1 || { echo "[install] 致命错误：zig 安装后仍不可用" >&2; exit 1; }
  log "zig: $(zig version)"
}

install_docker() {
  # 推荐容器化部署：环境需具备 Docker 以构建镜像并运行容器集成测试。
  # 嵌套 pod 无法 overlay-on-overlay，改用经典 graphdriver + fuse-overlayfs。
  if command -v docker >/dev/null 2>&1 && [ -f /etc/docker/daemon.json ]; then
    log "docker 已安装: $(docker --version)"
  else
    log "安装 Docker 与 fuse-overlayfs"
    sudo apt-get update -qq
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
      -o Dpkg::Options::=--force-confold \
      docker.io docker-buildx fuse-overlayfs
    sudo mkdir -p /etc/docker
    printf '%s\n' '{"features":{"containerd-snapshotter":false},"storage-driver":"fuse-overlayfs"}' \
      | sudo tee /etc/docker/daemon.json >/dev/null
    log "docker: $(docker --version)"
  fi
  # 让运行用户免 sudo 使用 docker（新登录 shell 生效）。
  if ! id -nG "${USER:-$(id -un)}" 2>/dev/null | tr ' ' '\n' | grep -qx docker; then
    sudo usermod -aG docker "${USER:-$(id -un)}" || true
  fi
}

sync_python() {
  log "同步 Python 依赖 (uv sync --locked --extra dev)"
  uv sync --locked --extra dev
}

write_dotenv() {
  if [ -f .env ]; then
    log ".env 已存在，跳过"
    return
  fi
  log "写入 .env（本地 stdio 默认配置）"
  cat > .env <<EOF
GHIDRA_INSTALL_DIR=${GHIDRA_INSTALL_DIR}
GHIDRA_MCP_ANALYSIS_TIMEOUT_SECONDS=300
GHIDRA_MCP_TRANSPORT=stdio
EOF
}

export PATH="$HOME/.local/bin:$PATH"
require_java
install_uv
install_ghidra
install_zig
install_docker
sync_python
write_dotenv
log "开发环境准备完成"
