# 久久派 AOSC 板载 Wi-Fi（AIC8800 SDIO）支持

**最终结果（2026-10-02 验证）**：板载 AIC8800 正常工作，`wlan0` 连接 `WIFI_LEE`（5 GHz）
并成功上网（`curl --interface wlan0 http://www.baidu.com` → HTTP 200）。

- SoC：Loongson 2K0300（loongarch64_nosimd）
- 系统：AOSC OS 12.2.1，内核由本仓库重建为 `6.12.35.lsgd`（含 SDIO CMD53 quirk）
- 模组：AIC8800D80 SDIO（`c8a1:0082` / `c8a1:0182`），SDIO1 `16148000.sdio`

## 为什么要重编内核

板载 SDIO 主机驱动 `ls2k_sdio`（源码来自 Ilikara/linux-6.12 的 `drivers/mmc/host/ls2kmci.c`，
**builtin**）缺少 **CMD53 quirk**。现象：加载 `aic8800_bsp` 后

```
aicbsp_dummy_sdmmc mmc1:42f1:1: probe ... failed with error -110   # -110 = ETIMEDOUT
aicbsp: fail to set AIC_WIFI power state to 1
```

必须给 `ls2k_mci_send_command()` 注入（zyly 方案）：

```c
if (cmd->opcode == 53) {
    u32 val = readl(host->base + SDIDCON);
    val |= (0x3 << 24);
    writel(val, host->base + SDIDCON);
}
```

## 组件

### GitHub Actions workflow

| 文件 | 作用 |
|---|---|
| `.github/workflows/build-aic8800-sdio.yml` | 交叉编译 aic8800 的 3 个 SDIO 模块（`aic8800_bsp/fdrv/btlpm.ko`）。用完整上游 `linux-6.12.35` 做 KDIR（AOSC headers 包缺 `arch/loongarch/include`），沿用 AOSC 的 `.config` 与 `Module.symvers` 保证 ABI。 |
| `.github/workflows/build-kernel-6.12.35-wifi.yml` | 用上游 `linux-6.12.35.tar.xz` + AOSC ABBS commit `27432fb40548`（6.12.35）的 376 个补丁精确重建板子内核，注入 CMD53 quirk，产出 `uImage`。 |

两个 workflow 都是 `workflow_dispatch`，在 Actions 页面手动触发，产物在 run 的 Artifacts 里下载。

### 补丁（`patches/`）

- `loongarch-PC-macro.patch`：`rwnx_msg_rx.c` 的 `struct fault_ctxt` 字段 `PC` 与
  LoongArch uapi `asm/ptrace.h` 的 `PC` 宏冲突，改名为 `fw_pc`。

### 脚本（`scripts/`）

| 脚本 | 说明 |
|---|---|
| `uimage-mkimage.py` | 手工构造 legacy uImage（`arch=loongarch`）。系统与自编 `mkimage` 都不认 loongarch。 |
| `install-aic8800.sh` | 板子端：放置固件到 `/lib/firmware/aic8800_fw/SDIO/aic8800D80/`、模块到 `/lib/modules/$(uname -r)/`、`depmod`、`modprobe`。 |
| `install-kernel.sh` | 板子端：备份并替换 `/boot/uImage`。 |
| `rollback-kernel.sh` | 板子端：从 `/boot/uImage.bak-*` 回滚。 |
| `connect-wifi.sh` | 板子端：配置 `wpa_supplicant@wlan0` + systemd-networkd DHCP 并连接。 |

### 固件（`firmware/aic8800D80/`）

取自 radxa-pkg/aic8800 的 `src/SDIO/driver_fw/fw/aic8800D80/`（u02 系列）。
安装后路径：`/lib/firmware/aic8800_fw/SDIO/aic8800D80/`。

## 复现步骤

1. **编译模块**：触发 `build-aic8800-sdio.yml`，下载 artifact（3 个 `.ko`）。
2. **重建内核**：触发 `build-kernel-6.12.35-wifi.yml`，下载 artifact（`uImage`）。
3. **部署到板子**（本机需能 ssh 到板子）：

   ```bash
   scp <artifact>/*.ko  aosc@<board>:/tmp/
   scp <artifact>/uImage aosc@<board>:/tmp/uImage.new
   scp -r firmware    aosc@<board>:/tmp/
   scp scripts/*.sh scripts/uimage-mkimage.py aosc@<board>:/tmp/
   ```

4. **板子端安装**：

   ```bash
   # 模块 + 固件
   sudo /tmp/install-aic8800.sh /tmp /tmp/firmware/aic8800D80
   # 内核（自动备份旧 uImage）
   sudo /tmp/install-kernel.sh /tmp/uImage.new
   sudo reboot
   ```

5. **连接 Wi-Fi**：

   ```bash
   sudo /tmp/connect-wifi.sh "<SSID>" "<密码>"
   ```

## 已知问题与回滚

- 若新内核无法启动：串口（`/dev/ttyUSB0` 115200 8N1）进 U-Boot，或
  在能进入系统时 `sudo /tmp/rollback-kernel.sh && sudo reboot`。
- 本机保留的旧内核备份：见部署机器上的 `board-backup/uImage.*`。

## 踩坑记录

1. AOSC 的 `linux-kernel-loongarch-2k0300` headers 包**不含 `arch/loongarch/include`**，
   无法据此编外部模块 —— 用完整上游源码做 KDIR，只借其 `.config`/`Module.symvers`。
2. LoongArch uapi `ptrace.h` 把 `PC` 定义为宏，与驱动局部变量冲突。
3. 上游 `linux-6.12.tar.xz` 是 6.12.0；AOSC spec 的 `${VER%%.0}`（pattern 为 `.0`）对
   `6.12.35` 不匹配，实际基线是 `linux-6.12.35.tar.xz`。
4. Ubuntu 的 `mkimage` 及 `tools-only_defconfig` 自编的 `mkimage` 都不认 `loongarch`，
   最终用 `scripts/uimage-mkimage.py` 手工按 legacy 头格式构造。
5. SDIO 主机驱动是 builtin，改动必须整内核重编 + 换 `uImage`（不能只换模块）。
