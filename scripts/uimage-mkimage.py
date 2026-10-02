#!/usr/bin/env python3
"""Minimal legacy uImage builder (mkimage replacement) for loongarch64.

与 mkimage 的 legacy image 模式兼容，只实现本项目需要的能力：
  uimage-mkimage.py -A loongarch -O linux -T kernel -C gzip \
      -a <load> -e <entry> -n <name> -d <data> <output>

之所以不用 mkimage：Ubuntu 的 u-boot-tools 不认 -A loongarch，
而自编 upstream u-boot 的 mkimage 在 tools-only_defconfig 下架构表为空。
本脚本按 legacy uImage 64 字节头格式手工构造，参数与板子原 uImage 对齐。
"""
import struct
import sys
import time
import zlib

ARCH = {
    "invalid": 0, "alpha": 1, "arm": 2, "x86": 3, "ia64": 4, "m68k": 5,
    "microblaze": 6, "mips": 7, "mips64": 8, "nios2": 9, "powerpc": 10,
    "s390": 11, "sh": 12, "sparc": 13, "sparc64": 14, "arm64": 22,
    "riscv": 26, "loongarch": 27, "x86_64": 28,
}
OS = {
    "openbsd": 1, "netbsd": 2, "freebsd": 3, "4_4bsd": 4, "linux": 5,
    "svr4": 6, "esix": 7, "solaris": 8, "irix": 9, "sco": 10, "dell": 11,
    "ncr": 12, "lynxos": 13, "vxworks": 14, "psos": 15, "qnx": 16,
    "u-boot": 17, "rtems": 18, "artos": 19, "unity": 20, "integrity": 21,
    "ose": 22, "plan9": 23,
}
TYPE = {
    "standalone": 1, "kernel": 2, "ramdisk": 3, "multi": 4, "firmware": 5,
    "script": 6, "filesystem": 7, "flatdt": 8, "kernel_noload": 14,
}
COMP = {"none": 0, "gzip": 1, "bzip2": 2, "lzma": 3, "lzo": 4, "lz4": 5, "zstd": 6}


def main(argv):
    opts = {}
    out = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-A", "-O", "-T", "-C", "-a", "-e", "-n", "-d"):
            opts[a] = argv[i + 1]
            i += 2
        elif a in ("-V", "--version"):
            print("uimage-mkimage (python shim)")
            return 0
        else:
            out = a
            i += 1

    if not out or "-d" not in opts:
        print("usage: uimage-mkimage.py -A <arch> -O <os> -T <type> "
              "-C <comp> -a <load> -e <entry> -n <name> -d <data> <output>",
              file=sys.stderr)
        return 2

    data = open(opts["-d"], "rb").read()
    load = int(opts.get("-a", "0"), 0) & 0xFFFFFFFF
    entry = int(opts.get("-e", "0"), 0) & 0xFFFFFFFF

    # legacy uImage header: 7 x u32 + 4 x u8 + 32-byte name = 64 bytes
    hdr = struct.pack(
        ">7I4B32s",
        0x27051956,
        0,
        int(time.time()),
        len(data),
        load,
        entry,
        zlib.crc32(data) & 0xFFFFFFFF,
        OS.get(opts.get("-O", "linux"), 5),
        ARCH.get(opts.get("-A", "loongarch"), 0),
        TYPE.get(opts.get("-T", "kernel"), 2),
        COMP.get(opts.get("-C", "none"), 0),
        opts.get("-n", "Linux").encode()[:31],
    )
    hcrc = zlib.crc32(hdr) & 0xFFFFFFFF
    hdr = hdr[:4] + struct.pack(">I", hcrc) + hdr[8:]

    with open(out, "wb") as f:
        f.write(hdr + data)

    print("uImage: %s arch=%s comp=%s load=0x%08x entry=0x%08x "
          "size=%d hcrc=0x%08x" % (out, opts.get("-A"), opts.get("-C"),
                                   load, entry, len(data), hcrc))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
