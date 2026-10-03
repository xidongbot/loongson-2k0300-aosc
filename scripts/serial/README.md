# 串口救援工具（久久派 / 通用 Linux 板）

主机侧通过 USB 串口（默认 `/dev/ttyUSB0`，115200 8N1）非交互式地操作板子控制台，
用于无人值守地抓启动日志、抢占 U-Boot、执行引导与修复命令。

依赖 Python 3 与 `pyserial`：

```bash
pip install pyserial
```

## serctl.py

| 用法 | 说明 |
|---|---|
| `serctl.py listen [秒]` | 只读串口并输出 |
| `serctl.py break [秒] [--key c] [--delay 0.08]` | 连发某键，用于抢占 U-Boot 控制台 |
| `serctl.py send "命令" [--seconds N]` | 发送一行（自动补 CR）后监读 N 秒 |

环境变量 `PORT`（默认 `/dev/ttyUSB0`）、`BAUD`（默认 `115200`）。

> 久久派 U-Boot 的 `Autoboot in 0 seconds` 无倒计时，提示
> `Press c to enter u-boot console`，需在上电瞬间用
> `serctl.py break 120 --key c --delay 0.08` 连发 `c` 才能进控制台。

## runseq.py

`runseq.py CMD文件 [每步间隔秒]`：一次性打开串口，顺序发送多行命令。
CMD 文件每行支持：

- `SLEEP <秒>`：只等待并读取输出；
- `KEY <十六进制>`：发送原始字节（如 `KEY 03` 即 Ctrl-C）；
- 其他行：发送该行 + CR，随后读取 N 秒。

## monitor.py

`monitor.py 超时秒 命令文件 [结束哨兵]`：发送命令文件内容后持续读取，
直到出现哨兵字符串或超时；适合等待板子上较长的后台任务。

> 命令里用 `echo FI""XDONE` 之类“拆字”构造哨兵，可避免被命令回显提前匹配。

## 示例

```bash
# 上电瞬间抢 U-Boot 控制台并记录
python3 serctl.py break 120 --key c --delay 0.08 > uboot.log 2>&1

# 顺序执行引导 / 救援命令
python3 runseq.py cmds.txt 3

# 等待板子上的后台任务（如 dpkg）完成
python3 monitor.py 900 wait.txt FIXDONE
```
