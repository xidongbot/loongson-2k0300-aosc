# 为久久派构建无 LSX 的 EasyTier（loongarch64 新世界）

板载 SoC 为 **Loongson 2K0300 / LA264**，**不支持 LSX/LASX** 向量扩展。AOSC 仓库里的
`easytier` 包与上游 release 的 loongarch64 二进制都含大量 LSX 指令（实测 `easytier-core`
有 20 万+ 条），在本板上运行即 `SIGILL`。本仓库用 GitHub Actions 交叉编译出**无 LSX** 的
`easytier-core` / `easytier-cli`。

## 关键结论

- Rust 的 loongarch64 target（`-gnu` 与 `-musl`）自 1.84 起**默认开启 `+lsx`**（target
  spec 写死 `+f,+d,+lsx,+relax`）；且预编译的 `std/core/alloc` 也带 LSX。
  因此仅 `RUSTFLAGS="-Ctarget-feature=-lsx"` 不够，**必须 `-Z build-std=std,panic_abort`
  连标准库一起重编**。
- C/C++ 依赖（`zstd-sys` / `kcp-sys` / `libmimalloc-sys` / `ring`）用交叉 gcc 加
  `-mno-lsx -mno-lasx` 编译。
- **不要用 zig**：zig 自带的 musl libc / compiler_rt 在 loongarch64 默认带 LSX
  （实测残留约 400 条，位于 `memcpy`/`printf_core`/`libunwind` 等），且是预编译的，
  `CFLAGS` 关不掉。改用交叉 glibc 工具链。

## 构建方案

在 **`debian:trixie` 容器**里用 Debian 的 loongarch64 交叉 glibc 工具链
（Ubuntu 没有交叉 libc）：

```
gcc-loongarch64-linux-gnu g++-loongarch64-linux-gnu
binutils-loongarch64-linux-gnu libc6-dev-loong64-cross
```

> ⚠️ 交叉 libc 包名是 **`libc6-dev-loong64-cross`**（Debian 架构名是 `loong64`），
> 不是 `libc6-dev-loongarch64-cross`。这是最容易卡住的一步。

容器内另需：`build-essential`（Rust 的 build script 要在宿主 x86_64 上编译，需要 `cc`）、
`libclang-dev`（`kcp-sys` 用 bindgen，需 libclang）、`unzip` + `arduino/setup-protoc`
（C 依赖需要 `protoc`）、`file`。

Rust 侧：1.95 + `rust-src` + `llvm-tools`，用 `RUSTC_BOOTSTRAP=1` 在 stable 上解锁
`-Z build-std`。

核心命令与环境：

```bash
cargo build --release --target loongarch64-unknown-linux-gnu \
  -Z build-std=std,panic_abort \
  -p easytier --features mimalloc
```

```
RUSTFLAGS=-Ctarget-feature=-lsx
CARGO_TARGET_LOONGARCH64_UNKNOWN_LINUX_GNU_LINKER=loongarch64-linux-gnu-gcc
CC_loongarch64_unknown_linux_gnu=loongarch64-linux-gnu-gcc
CXX_loongarch64_unknown_linux_gnu=loongarch64-linux-gnu-g++
AR_loongarch64_unknown_linux_gnu=loongarch64-linux-gnu-ar
CFLAGS_loongarch64_unknown_linux_gnu=-mno-lsx -mno-lasx -fno-tree-vectorize
CXXFLAGS_loongarch64_unknown_linux_gnu=-mno-lsx -mno-lasx -fno-tree-vectorize
BINDGEN_EXTRA_CLANG_ARGS_loongarch64-unknown-linux-gnu=--sysroot=/usr/loongarch64-linux-gnu
LIBCLANG_PATH=<含 libclang.so 的目录>
```

## 零 SIMD 门禁

产物必须过门禁：用 `llvm-objdump` 反汇编，任何以 `v`/`xv` 开头（LSX/LASX）的指令都判失败。

```bash
llvm-objdump -d --no-show-raw-insn easytier-core \
  | grep -cE '^[[:space:]]*[0-9a-f]+:[[:space:]]+x?v'
# 期望输出 0
```

## 产物与使用

Workflow：`.github/workflows/build-easytier-loongarch64-nosimd.yml`

- `workflow_dispatch` 触发，`easytier_ref` 留空则自动取上游最新 release；
- 产出 `easytier-core` / `easytier-cli`，上传 artifact，并发布到固定 Release tag
  `easytier-nosimd`（`prerelease`），便于板子直接 `curl` 下载。

板子端：

```bash
curl -fL -o /tmp/easytier.tar.gz \
  https://github.com/xidongbot/loongson-2k0300-aosc/releases/download/easytier-nosimd/easytier-loongarch64-nosimd.tar.gz
tar -C /tmp -xzf /tmp/easytier.tar.gz
sudo install -m755 /tmp/easytier-core /tmp/easytier-cli /usr/local/bin/
hash -r
easytier-core --version
```

验证：`easytier-core --version` 正常输出（不再 `SIGILL`）；`easytier-cli peer` 能看到本节点
与对端、隧道建立。产物为**动态链接 glibc** 的新世界可执行文件；AOSC 的 glibc 版本更新，
前向兼容。

## 踩坑清单

1. **交叉 libc 包名**：Ubuntu 与 Debian 都叫 `libc6-dev-loong64-cross`（`loong64` 是
   Debian 的 LoongArch64 架构名），写 `loongarch64` 会 `Unable to locate package`。
2. **只加 `-Ctarget-feature=-lsx` 不够**：预编译 `std/core/alloc` 自带 LSX，必须
   `-Z build-std`。
3. **zig 不可用**：其 musl/compiler_rt 带 LSX 且预编译关不掉。
4. **容器缺宿主工具**：`build-essential`（build script 的 `cc`）、`libclang-dev` +
   `LIBCLANG_PATH`（bindgen）、`unzip`（setup-protoc）、`file`。
5. **向量化开关是编译器相关的**：clang 的 `-fno-vectorize` / `-fno-slp-vectorize` 在 GCC
   下不被识别（报 `unrecognized command-line option`）；GCC 用 `-mno-lsx` 即可。
6. **C 依赖需要 `protoc`**：`prost-wkt-types` 的 build script 需要 `protoc` 及其
   well-known types，用 `arduino/setup-protoc` 最稳（系统 `protobuf-compiler` 可能缺
   `google/protobuf/*.proto`）。

## 参考

- 上游 EasyTier：<https://github.com/EasyTier/EasyTier>
- Rust loongarch64 target 默认 `+lsx`：<https://doc.rust-lang.org/stable/rustc/platform-support/loongarch-linux.html>
- LoongArch GCC 选项（`-mno-lsx` / `-march=loongarch64`）：<https://gcc.gnu.org/onlinedocs/gcc/LoongArch-Options.html>
