#!/usr/bin/env python3
"""
net_telemetry.py (Linux)
Baseline network/system telemetry logger.

- Collects interface stats, listening ports, neighbor table, and warnings.
- Appends JSON lines to log files in a directory.
- Safe, read-only, no packet sniffing required.

Usage:
  python3 net_telemetry.py --out ./telemetry --interval 30
"""

import argparse
import json
import os
import socket
import subprocess
import time
from datetime import datetime


def run(cmd: str) -> str:
    try:
        out = subprocess.check_output(["bash", "-lc", cmd], stderr=subprocess.STDOUT, text=True)
        return out.strip()
    except Exception as e:
        return f"ERROR: {e}"


def write_jsonl(path: str, obj: dict) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="./telemetry", help="output directory")
    ap.add_argument("--interval", type=int, default=30, help="seconds between samples")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    host = socket.gethostname()
    print(f"Logging telemetry on {host} every {args.interval}s -> {args.out}")

    while True:
        ts = datetime.now().isoformat()

        sample = {
            "ts": ts,
            "host": host,
            "iface_stats": run("ip -s link"),
            "listening": run("ss -tulpn"),
            "neighbors": run("ip neigh"),
            "routes": run("ip route"),
            "warnings": run("journalctl -p warning..alert -n 50 --no-pager 2>/dev/null || true"),
        }

        write_jsonl(os.path.join(args.out, "net_telemetry.jsonl"), sample)

        # Small “heartbeat” line so you can see it’s alive
        print(f"[{ts}] wrote sample")

        time.sleep(args.interval)


if __name__ == "__main__":
    main()
