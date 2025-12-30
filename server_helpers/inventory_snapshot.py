#!/usr/bin/env python3
"""
inventory_snapshot.py
Collects a quick baseline inventory of a Linux host and writes JSON.

Usage:
    python3 inventory_snapshot.py
    python3 inventory_snapshot.py --out /var/tmp
"""

import argparse
import json
import os
import platform
import socket
import subprocess
import time
from datetime import datetime


def run(cmd: list[str]) -> str:
    """Run command and return stdout, or empty string if it fails."""
    try:
        return subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True).strip()
    except Exception:
        return ""


def file_read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def get_uptime_seconds() -> float:
    up = file_read("/proc/uptime")
    if not up:
        return 0.0
    return float(up.split()[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".", help="output directory for json snapshot")
    args = ap.parse_args()

    hostname = socket.gethostname()
    now = datetime.now().strftime("%Y%m%d-%H%M%S")

    data = {
        "timestamp": datetime.now().isoformat(),
        "hostname": hostname,
        "fqdn": socket.getfqdn(),
        "os": {
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
        },
        "kernel": run(["uname", "-a"]),
        "uptime_seconds": get_uptime_seconds(),
        "cpu": {
            "model": file_read("/proc/cpuinfo").split("model name")[:2][-1].split(":")[-1].strip()
                     if os.path.exists("/proc/cpuinfo") else "",
            "lscpu": run(["bash", "-lc", "lscpu"]),
        },
        "memory": {
            "free_h": run(["bash", "-lc", "free -h"]),
            "meminfo": run(["bash", "-lc", "grep -E 'MemTotal|MemFree|MemAvailable|SwapTotal|SwapFree' /proc/meminfo"]),
        },
        "disks": {
            "lsblk": run(["bash", "-lc", "lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL,SERIAL -J 2>/dev/null || lsblk"]),
            "df_h": run(["bash", "-lc", "df -hT"]),
        },
        "network": {
            "ip_addr": run(["bash", "-lc", "ip -br addr"]),
            "ip_route": run(["bash", "-lc", "ip route"]),
            "resolv_conf": file_read("/etc/resolv.conf"),
        },
        "services": {
            "systemctl_failed": run(["bash", "-lc", "systemctl --failed --no-pager"]),
            "systemctl_running_count": run(["bash", "-lc", "systemctl list-units --type=service --state=running --no-pager | wc -l"]),
        },
    }

    os.makedirs(args.out, exist_ok=True)
    out_path = os.path.join(args.out, f"inventory-{hostname}-{now}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Wrote snapshot: {out_path}")


if __name__ == "__main__":
    main()
