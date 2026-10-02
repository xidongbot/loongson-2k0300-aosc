#!/usr/bin/env bash
# 在久久派 AOSC 板子上连接 Wi-Fi（wpa_supplicant@wlan0 + systemd-networkd DHCP）
#
# 用法：
#   sudo ./connect-wifi.sh <SSID> <PASSWORD>
set -euo pipefail

SSID="${1:?用法: sudo ./connect-wifi.sh <SSID> <PASSWORD>}"
PASS="${2:?用法: sudo ./connect-wifi.sh <SSID> <PASSWORD>}"
IFACE="wlan0"
WPACONF="/etc/wpa_supplicant/wpa_supplicant-${IFACE}.conf"
NETCONF="/etc/systemd/network/25-${IFACE}.network"

command -v wpa_passphrase >/dev/null || { echo "缺少 wpa_passphrase" >&2; exit 1; }

echo "== 写入 wpa_supplicant 配置 =="
wpa_passphrase "$SSID" "$PASS" | grep -v '^[[:space:]]*#psk' > "$WPACONF"
chmod 600 "$WPACONF"

echo "== 写入 networkd DHCP 配置 =="
printf '[Match]\nName=%s\n\n[Network]\nDHCP=yes\n' "$IFACE" > "$NETCONF"

echo "== 启用并重启服务 =="
systemctl enable --now "wpa_supplicant@${IFACE}.service"
systemctl restart systemd-networkd

echo "== 等待连接与 DHCP =="
for i in $(seq 1 20); do
  sleep 2
  if ip -4 addr show "$IFACE" | grep -q 'inet '; then break; fi
done

ip -br addr show "$IFACE" || true
echo "== 关联信息 =="
iw dev "$IFACE" link 2>/dev/null | head -6 || true
echo "== 联网测试（curl 绑定 wlan0） =="
curl -s --interface "$IFACE" -o /dev/null -w "http=%{http_code} remote_ip=%{remote_ip} time=%{time_total}s\n" \
  --max-time 20 http://www.baidu.com || echo "curl 失败"
