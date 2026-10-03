#!/usr/bin/env python3
"""Send a command sequence over serial in one session.

Usage: runseq.py CMDFILE [GAP_SECONDS]

CMDFILE lines:
  SLEEP <sec>     - just drain output
  KEY <hexbytes>  - send raw bytes (e.g. "KEY 03" = Ctrl-C)
  <anything else> - send line + CR, then drain GAP seconds
"""
import sys
import time

import serial

PORT = "/dev/ttyUSB0"
BAUD = 115200

cmdfile = sys.argv[1]
gap = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0

s = serial.Serial(PORT, BAUD, bytesize=8, parity="N", stopbits=1, timeout=0.2)


def emit(d):
    if d:
        sys.stdout.buffer.write(d)
        sys.stdout.buffer.flush()


def drain(sec):
    end = time.time() + sec
    while time.time() < end:
        emit(s.read(4096))


for raw in open(cmdfile):
    line = raw.rstrip("\n")
    if not line.strip():
        continue
    if line.startswith("SLEEP "):
        drain(float(line.split()[1]))
        continue
    if line.startswith("KEY "):
        s.write(bytes.fromhex(line.split(None, 1)[1]))
        s.flush()
        continue
    s.write(line.encode() + b"\r")
    s.flush()
    drain(gap)

drain(3)
s.close()
