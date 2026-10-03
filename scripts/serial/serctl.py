#!/usr/bin/env python3
"""Tiny non-interactive serial driver for the 久久派 rescue console.

Usage:
  serial.py listen [SECONDS]
  serial.py break  [SECONDS] [--delay 0.2]     # spam CR to stop autoboot
  serial.py send   "TEXT"    [--seconds 10]    # send TEXT + CR, then listen

Env: PORT (/dev/ttyUSB0), BAUD (115200)
"""
import argparse
import os
import sys
import time

import serial

PORT = os.environ.get("PORT", "/dev/ttyUSB0")
BAUD = int(os.environ.get("BAUD", "115200"))


def open_port():
    return serial.Serial(
        PORT, BAUD,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.2,
    )


def emit(data):
    if data:
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()


def pump(s, deadline, send=None, delay=0.2):
    next_send = 0.0
    while time.time() < deadline:
        now = time.time()
        if send is not None and now >= next_send:
            s.write(send)
            s.flush()
            next_send = now + delay
        emit(s.read(4096))
    time.sleep(0.3)
    emit(s.read(65536))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["listen", "break", "send"])
    ap.add_argument("value", nargs="?", default="")
    ap.add_argument("--seconds", type=float, default=10.0)
    ap.add_argument("--delay", type=float, default=0.2)
    ap.add_argument("--key", default="\r")
    a = ap.parse_args()

    s = open_port()
    try:
        if a.mode == "listen":
            secs = float(a.value or a.seconds)
            pump(s, time.time() + secs)
        elif a.mode == "break":
            secs = float(a.value or a.seconds)
            pump(s, time.time() + secs, send=a.key.encode(), delay=a.delay)
        elif a.mode == "send":
            s.write(a.value.encode() + b"\r")
            s.flush()
            pump(s, time.time() + a.seconds)
    finally:
        s.close()


if __name__ == "__main__":
    main()
