# 久久派（Loongson 2K0300 99PAI WiFi）刷 AOSC OS 到 eMMC 实录

本仓库记录把 **AOSC OS**（[Ilikara](https://cnb.cool/hex/loong/Loongson-2K0300-99PAI) 移植）安装到 **久久派 2K0300 Wi-Fi 版**（板载 eMMC、无 TF 卡槽）的完整过程，以及过程中踩到的所有坑。最终结果：**板子从 eMMC 启动 AOSC OS 12.2.1 / Linux 6.12.35.lsgd，登录 aosc / anthon**。

## 硬件与固件背景

- SoC：Loongson 2K0300，LA264，DDR 512 MiB（两个 bank：`0x9000000000000000` + `0x9000000090000000`）
- 存储：SPI NOR 1 MiB（分区 `uboot`/`uboot_env`/`bdinfo`/`dtb`/...）、板载 eMMC 7.28 GiB（`/dev/mmcblk0`）
- Wi-Fi 版**没有 TF 卡槽**（Wi-Fi 模组与 TF 卡座共用 SDIO1），只能用 eMMC
- 串口：UART0，IO 2×15P 排针的 4 脚 TXD / 6 脚 RXD / 1 脚 GND，**仅作控制台**，115200 8N1
- 板载只有一个复位键，**没有任何 BOOT/烧录按键**；启动介质由 SoC 上电 strap 决定

## 最终可行的完整流程

### 1. 编译并刷入正确的 U-Boot（替换板上的错误固件）

板子出厂/残余的 U-Boot 与这块 Wi-Fi 板不匹配（`general_load` 崩、`loongson_update` 找 `nand0`）。

用 GitHub Actions 交叉编译 `open-loongarch/u-boot`（`loongson_2k300_99pi_wifi_defconfig`），见 <https://github.com/xidongbot/loongson-2k0300-uboot>。要点：

- GitHub runner 直连 gitee 会 `TLS connection was non-properly terminated`，故把源码快照作为 release 资产再从 GitHub 内网取；
- Ubuntu 交叉 gcc 可执行名带版本后缀（`loongarch64-linux-gnu-gcc-14`），要补无后缀软链；
- 产物：`u-boot-with-spl.bin`、`u-boot.dtb`。

在 U-Boot 里手动写 SPI（此时板子还有可用的 U-Boot console）：

```
usb start
ext4load usb 0:0 0x9000000003000000 /update/u-boot-with-spl.bin
sf probe
sf erase 0 0xE7000
sf write 0x9000000003000000 0 0xE6000
```

**写 SPI 期间绝不能断电。**

### 2. 制作 AOSC 整盘镜像并写入 U 盘

AOSC 提供的是 rootfs tar（展开 2.9 GB，内含 `/boot/uImage`，**不含 dtb**）。U-Boot 的 `general_load` 只接受“含 MBR 分区表的磁盘镜像 + gzip”（`rootfs.img = rootfs.ext2.gz` 那种），所以：

```
解压 tar → mkfs.ext4 -d 填充分区内容 → 组装 MBR（p1 起始 2048 扇区）→ gzip → rootfs.img
```

再把 `rootfs.img` **整盘写入 U 盘**（U 盘就成为可引导的 AOSC 系统盘）。

### 3. 提取内核自带的板级 DTB

AOSC 内核 uImage 内部自带 6 个 DTB；其中 `emb4` 的根节点 `product = "LS2K300-99PI-WIFI"`，**没有 `/memory` 节点、中断齐全**——这才是给这个内核用的 DTB。把它放到 U 盘 `/boot/aosc-99pi-wifi.dtb`。

### 4. U-Boot 从 U 盘启动 AOSC

```
usb start
ext4load usb 0:1 0x9000000003000000 /boot/uImage
ext4load usb 0:1 0x900000000a000000 /boot/aosc-99pi-wifi.dtb
setenv fdt_addr 0x900000000a000000
setenv bootargs console=ttyS0,115200 root=/dev/sda1 rootwait rw
bootm                     # 注意：不要带 "- <fdt>"！
```

进入系统（aosc/anthon）后，把整盘写进 eMMC：

```
sudo dd if=/dev/sda of=/dev/mmcblk0 bs=1M count=3694 conv=fsync status=progress
```

### 5. 把正确 DTB 固化进 SPI（否则从 eMMC 启动会 panic）

可以从已启动的 AOSC 里写 `/dev/mtdblock0`（SPI 整块），把 emb4 写到 dtb 分区偏移 `0xf0000`（块 240），或回到 U-Boot 用 `sf erase/write`。

## 踩坑清单

1. **论坛“新固件”V1.0 其实是 PMON**（`PMON2000`、`pmon.bin`），与 AOSC 需要的 U-Boot 是两条互斥引导链，刷了反而退回旧世界。
2. **厂商 `general_load --decompress` 单次只处理约 156 MiB 压缩块**（源码 `ldbr_init` 里 `--decompress` 会置 `once_only=true`，受 `lmb_get_free_size` 限制），AOSC 压缩后 740 MiB 根本放不下；且**无压缩路径 `m__br_blk` 有逐块多写 1 块的错位 bug**。
3. **U-Boot 经 USB(EHCI) 读大文件不稳定**：读那个 3.87 GB 的 raw 文件时，请求 4 MiB 起就 `EHCI timed out on TD`；而读 11.7 MiB 的 uImage、919 KiB 的 u-boot、8 KB 的 dtb 都正常。
4. **`fs_read_lmb_check`（`fs/fs.c`）会拒绝把文件读到 LMB 保留区**，大块加载会报 `overwrite reserved memory`；且 `ext4load` 的可选参数顺序是 `[bytes [pos]]`（不是 `pos length`）。
5. **U-Boot fork 的 `bootm` bug**：用 `bootm <kernel> - <fdt>` 显式传 DT 时，`linux_argv` 未初始化（NULL），而内核名 `Linux-6.12.35.lsgd` 被判为“新传参规范”，于是执行 `linux_argv[1]` 访问地址 `0x8` → 在无页表的 U-Boot 里 TLB 异常死机。**内核一步都没执行**。改用 **`bootm`（不带 dtb 参数）**，DT 由 `fdt_addr` 经 EFI_FDT_GUID 传给内核。
6. **U-Boot 编译出的 DTB 不能直接给内核用**：
   - 它的 `/memory` 写的是 **CACHED 窗口虚拟地址**（`0x9000000000000000` 等），内核把它当物理地址 → memblock 出现 pfn 超限 → `sparse_init` 里的 `WARN_ON_ONCE`（`break 1`）在 `trap_init()` 之前触发，落进 `handle_reserved` → 以 “Attempted to kill the idle task!” panic；
   - 它**缺中断号**，内核里 USB/网口 `IRQ index 0 not found`，U 盘认不到。
   - 结论：用**内核自带的板级 DTB**（无 `/memory`，内存由 U-Boot 的 BPI 表提供）。
7. **串口只是控制台**，固件数据走 USB/网口；`phoenixsuit`（全志）、`ls2k0300` 之类工具与本板无关；EJTAG 是唯一的救砖通道。
8. **eMMC 版没有 TF 卡槽**，不能像 TF 版那样拔卡在 PC 上写；官方“U 盘 LiveCD + update.sh”是 eMMC 版的正规装法。
9. **板上 U-Boot 环境可能是错的**（`mtdids` 指向不存在的 `ls-nand`、`bootcmd` 为空），刷入正确 U-Boot 后要 `env default -a; env save` 重置为编译默认。

## 一句话总结

厂商的 eMMC 更新机制（`general_load`）是为 ~150 MB 的小镜像设计的；AOSC 的 740 MB 压缩 rootfs 超出了它的能力，只能走“U 盘做系统盘 → U-Boot 正确引导 → Linux 内 dd 写 eMMC”这条路。而这条路上真正的拦路虎是 **U-Boot fork 的 `bootm` bug** 和 **U-Boot DTB 不能给内核用** 这两点。
