# AOSC OS 升级中断与 PAM 断裂救援记录

> 时间：2026-10-03　| 对象：久久派 2K0300（Wi-Fi 版，eMMC 上的 AOSC OS）

## 现象

执行 `sudo oma install btop git easytier zellij labwc`（顺带批量升级）时，
解包/配置阶段中断。之后：

- `dpkg` 报 `libpwquality` 依赖 `cracklib`、`python-3` 未配置；
- 更严重的是 `sudo`、`login`、`su` 等一切走 PAM 的程序全部失效：

```text
sudo: unable to load /usr/libexec/sudo/sudoers.so:
/usr/lib/libeconf.so.0: version `LIBECONF_0.6' not found
(required by /usr/lib/libpam.so.0)
```

系统因此连串口/SSH 都无法登录，只能从外部救援。

## 根因

这是一次“旧 sysroot 跨代升级”：Python 3.10→3.14、libeconf 0.5→0.8、
linux-pam→1.7.2 同时发生。其中 linux-pam 自 1.7 起依赖 libeconf，需要
`LIBECONF_0.6` 符号版本，而系统里 libeconf 仍为 0.5.0。

这是 AOSC 已知问题，修复见 aosc-os-abbs PR #16235（libeconf 增加
`Breaks: linux-pam<=1.7.2`、linux-pam 增加 `PKGPRDEP=libeconf`，2026-07-16
进入 stable）。早于该修复的旧系统批量升级时会命中。

另外，本次事务其实已把整批 deb 下载到 `/var/cache/apt/archives`
（失败事务不会清理该目录），只是解包/配置中断，留下“新版已解包、
其依赖新版却未装”的断裂。

## 救援思路

eMMC 上的系统已无法登录，故：

1. 用可引导的 AOSC U 盘启动（U-Boot 里抢控制台后从 U 盘引导）；
2. 挂载 eMMC 根分区并 `chroot` 进入（chroot 内即为 root，不依赖 PAM）；
3. 先用缓存里的 libeconf 0.8.3 修复 PAM；
4. 用 `dpkg -i` 安装缓存中的全部 deb，再 `dpkg --configure -a`
   （可能需补装被漏掉的依赖，如 libtiff / giflib / llvm-runtime）。

主机侧的串口自动化脚本见 [`scripts/serial/`](../scripts/serial/README.md)。

## 关键命令

U-Boot 控制台（上电瞬间连发 `c` 进入）：

```
usb start
ext4load usb 0:1 0x9000000003000000 /boot/uImage
ext4load usb 0:1 0x900000000a000000 /boot/aosc-99pi-wifi.dtb
setenv fdt_addr 0x900000000a000000
setenv bootargs console=ttyS0,115200 root=/dev/sda1 rootwait rw
bootm
```

U 盘系统内挂载 eMMC 并进入：

```bash
lsblk                                  # 确认 eMMC 根分区
sudo mkdir -p /mnt/emmc
sudo mount /dev/mmcblk0p1 /mnt/emmc
for d in dev proc sys run; do sudo mount --rbind /$d /mnt/emmc/$d; done
sudo chroot /mnt/emmc /bin/bash
```

chroot 内修复：

```bash
# 1) 先修 PAM：安装缓存中正确的 libeconf
DEBIAN_FRONTEND=noninteractive dpkg -i /var/cache/apt/archives/libeconf_*_loongarch64.deb
ldconfig
sudo -V                                # 能加载即 PAM 恢复

# 2) 安装缓存中全部 deb，再完成配置
DEBIAN_FRONTEND=noninteractive dpkg -i /var/cache/apt/archives/*.deb
DEBIAN_FRONTEND=noninteractive dpkg --configure -a

# 3) 若仍有依赖卡住，补装被漏掉的关键依赖后重跑 configure
#    本次为 libtiff / giflib / llvm-runtime

# 4) 校验
dpkg --audit
```

退出并重启回 eMMC：

```bash
exit
sync
sudo umount -R /mnt/emmc
reboot
```

## 结果

- eMMC 系统正常启动（自编内核与板载 Wi-Fi 驱动均保留），`sudo` 恢复，
  `dpkg --audit` 为空；
- `oma install` 请求的软件全部就位；
- 系统版本随本次升级前进。

## 预防

- 有 Python/libeconf 这类迁移时，用整批 `oma upgrade`，不要用安装个别包
  顺带触发大批连带升级；
- 升级前确认磁盘可用空间充足（官方建议 ≥5 GiB）；
- 想保留离线救援底牌，日常升级加 `oma ... --no-clean`
  （成功事务默认会清空 `/var/cache/apt/archives`）。

## 参考

- AOSC 官方救援（LiveKit）：<https://wiki.aosc.io/aosc-os/installation/livekit/>
- libeconf/linux-pam 断裂修复：<https://github.com/AOSC-Dev/aosc-os-abbs/pull/16235>
- 同类故障：<https://bbs.aosc.io/t/topic/702>
