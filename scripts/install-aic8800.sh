#!/usr/bin/env bash
# 在久久派 AOSC 板子上安装 AIC8800 SDIO 驱动（Wi-Fi 版，eMMC 启动）
#
# 用法（在板子上、驱动产物目录内）：
#   sudo ./install-aic8800.sh [KO目录] [固件目录]
# 默认从脚本所在目录向上找 .ko 与 firmware/aic8800D80。
#
# 注意：本脚本只做“放固件 + 放模块 + depmod + modprobe”，
#       不编译。模块须由 GitHub Actions 交叉编译产出（见 .github/workflows/）。
set -euo pipefail

KO_DIR="${1:-}"
FW_DIR="${2:-}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KVER="$(uname -r)"
FW_DST="/lib/firmware/aic8800_fw/SDIO/aic8800D80"

if [ -z "$KO_DIR" ]; then
  KO_DIR="$(dirname "$HERE")"        # 仓库根
fi
if [ -z "$FW_DIR" ]; then
  FW_DIR="$HERE/firmware/aic8800D80"
fi

echo "KVER   = $KVER"
echo "KO_DIR = $KO_DIR"
echo "FW_DIR = $FW_DIR"

# 1) 固件
if [ -d "$FW_DIR" ]; then
  sudo install -d "$FW_DST"
  sudo cp -v "$FW_DIR"/. "$FW_DST"/ 2>/dev/null || sudo cp -v "$FW_DIR"/* "$FW_DST"/
else
  echo "WARN: 找不到固件目录 $FW_DIR，跳过" >&2
fi

# 2) 模块
if ls "$KO_DIR"/*.ko >/dev/null 2>&1; then
  sudo cp -v "$KO_DIR"/*.ko "/lib/modules/$KVER/"
  sudo depmod -a "$KVER"
else
  echo "ERROR: $KO_DIR 下没有 .ko，先编译驱动" >&2
  exit 1
fi

# 3) 依赖与加载
sudo modprobe cfg80211 || true
sudo modprobe rfkill || true
sudo modprobe aic8800_bsp
sudo modprobe aic8800_fdrv

echo "== ip link =="
ip -br link
echo "== dmesg (aic/sdio) =="
sudo dmesg | grep -iE "aic|sdio|cfg80211" | tail -30
