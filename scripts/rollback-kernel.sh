#!/usr/bin/env bash
# 回滚久久派 AOSC 内核 uImage
#
# 用法：
#   sudo ./rollback-kernel.sh                # 自动选最新的 /boot/uImage.bak-*
#   sudo ./rollback-kernel.sh /boot/uImage.bak-YYYYmmdd-HHMMSS
set -euo pipefail
BOOT="/boot"
BAK="${1:-}"
if [ -z "$BAK" ]; then
  BAK="$(ls -1t "$BOOT"/uImage.bak-* 2>/dev/null | head -1 || true)"
fi
[ -n "$BAK" ] && [ -f "$BAK" ] || { echo "找不到备份 uImage.bak-*" >&2; exit 1; }

echo "从 $BAK 回滚"
sudo cp -v "$BAK" "$BOOT/uImage"
sudo sync
echo "已回滚，执行 sudo reboot 重启。"
