#!/usr/bin/env bash
# 在久久派 AOSC 板子上安装新内核 uImage（自动备份旧内核，失败可回滚）
#
# 用法：
#   sudo ./install-kernel.sh /path/to/uImage
#
# 说明：U-Boot 从 eMMC /boot/uImage 加载内核，DTB 来自 SPI dtb 分区。
#       本脚本只替换 uImage，并保留带时间戳的备份。
set -euo pipefail

NEW="${1:?用法: sudo ./install-kernel.sh /path/to/uImage}"
[ -f "$NEW" ] || { echo "找不到 $NEW" >&2; exit 1; }

BOOT="/boot"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$BOOT/uImage.bak-$STAMP"

echo "旧内核 md5: $(md5sum "$BOOT/uImage" | awk '{print $1}')"
echo "新内核 md5: $(md5sum "$NEW" | awk '{print $1}')"

sudo cp -v "$BOOT/uImage" "$BACKUP"
sudo cp -v "$NEW" "$BOOT/uImage"
sudo sync

echo
echo "安装完成。"
echo "  备份: $BACKUP"
echo "  回滚: sudo cp '$BACKUP' $BOOT/uImage && sync && sudo reboot"
echo "  重启: sudo reboot"
