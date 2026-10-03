#!/usr/bin/env python3
"""Send serial commands, then read until SENTINEL appears or timeout.

Usage: monitor.py SECONDS CMDFILE [SENTINEL]
"""
import sys
import time

import serial

PORT = "/dev/ttyUSB0"
BAUD = 115200

timeout = float(sys.argv[1])
cmdfile = sys.argv[2]
sentinel = (sys.argv[3] if len(sys.argv) > 3 else "FIXDONE").encode()

cmds = [l.rstrip("\n") for l in open(cmdfile) if l.strip()]

s = serial.Serial(PORT, BAUD, bytesize=8, parity="N", stopbits=1, timeout=0.2)


def emit(d):
    if d:
        sys.stdout.buffer.write(d)
        sys.stdout.buffer.flush()


buf = b""
for c in cmds:
    s.write(c.encode() + b"\r")
    s.flush()
    time.sleep(0.5)

end = time.time() + timeout
ok = False
while time.time() < end:
    d = s.read(4096)
    if d:
        emit(d)
        buf += d
        if sentinel in buf:
            ok = True
            break

t = time.time() + 3
while time.time() < t:
    d = s.read(4096)
    if d:
        emit(d)

s.close()
sys.exit(0 if ok else 2)
