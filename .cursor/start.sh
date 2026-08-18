#!/usr/bin/env bash
# 每次容器启动时确保 Docker daemon 就绪。
# 嵌套 pod 环境无法用 overlay-on-overlay，必须以 fuse-overlayfs 作为存储驱动
# （由 .cursor/install.sh 写入 /etc/docker/daemon.json）。
set -euo pipefail

log() { printf '[start] %s\n' "$*"; }

if ! command -v dockerd >/dev/null 2>&1; then
  echo "[start] 致命错误：未找到 dockerd，请先执行 install（.cursor/install.sh）。" >&2
  exit 1
fi

if sudo docker info >/dev/null 2>&1; then
  log "Docker daemon 已在运行"
  exit 0
fi

log "启动 dockerd"
sudo sh -c 'nohup dockerd >/var/log/dockerd.log 2>&1 &'
for _ in $(seq 1 30); do
  if sudo docker info >/dev/null 2>&1; then
    log "Docker daemon 就绪（storage driver: $(sudo docker info --format '{{.Driver}}' 2>/dev/null)）"
    exit 0
  fi
  sleep 1
done

echo "[start] 致命错误：dockerd 启动超时" >&2
sudo tail -n 20 /var/log/dockerd.log >&2 2>/dev/null || true
exit 1
