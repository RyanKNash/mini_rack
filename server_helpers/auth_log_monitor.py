#!/usr/bin/env python3
"""
auth_log_monitor.py (Ubuntu/Debian)
Monitors /var/log/auth.log and emits structured JSONL events.

Events captured (best-effort):
- sshd failed password
- sshd accepted password/publickey
- sudo commands
- useradd/adduser (sometimes logged via auth or syslog, depends on config)

Usage:
  sudo python3 auth_log_monitor.py --out /var/log/iot_auth_events.jsonl
  sudo python3 auth_log_monitor.py --out ./iot_auth_events.jsonl

Tip:
  Run with sudo to ensure it can read /var/log/auth.log.
"""

import argparse
import json
import os
import re
import socket
import time
from datetime import datetime

AUTH_LOG_DEFAULT = "/var/log/auth.log"

# Regex patterns (auth.log format varies slightly across distros)
RE_FAILED = re.compile(r"sshd\[\d+\]: Failed password for (invalid user )?(?P<user>\S+) from (?P<ip>\S+)")
RE_ACCEPTED = re.compile(r"sshd\[\d+\]: Accepted (password|publickey) for (?P<user>\S+) from (?P<ip>\S+)")
RE_SUDO = re.compile(r"sudo: +(?P<user>\S+) : .*COMMAND=(?P<cmd>.+)$")


def jsonl_append(path: str, obj: dict) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj) + "\n")


def follow_file(path: str):
    """
    Generator that yields new lines as they are appended (like `tail -F`).
    Handles log rotation by reopening if inode changes.
    """
    def inode(p):
        try:
            return os.stat(p).st_ino
        except FileNotFoundError:
            return None

    current_inode = inode(path)
    f = None

    while True:
        if f is None:
            try:
                f = open(path, "r", encoding="utf-8", errors="replace")
                f.seek(0, os.SEEK_END)  # start at end
                current_inode = inode(path)
            except FileNotFoundError:
                time.sleep(1)
                continue

        line = f.readline()
        if line:
            yield line.rstrip("\n")
        else:
            # check rotation
            new_inode = inode(path)
            if new_inode is not None and current_inode is not None and new_inode != current_inode:
                try:
                    f.close()
                except Exception:
                    pass
                f = None
            time.sleep(0.2)


def parse_line(line: str):
    """Return (event_type, fields) or (None, None)."""
    m = RE_FAILED.search(line)
    if m:
        return "ssh_failed", {"user": m.group("user"), "ip": m.group("ip")}

    m = RE_ACCEPTED.search(line)
    if m:
        return "ssh_accepted", {"user": m.group("user"), "ip": m.group("ip")}

    m = RE_SUDO.search(line)
    if m:
        return "sudo", {"user": m.group("user"), "cmd": m.group("cmd").strip()}

    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--authlog", default=AUTH_LOG_DEFAULT, help="path to auth.log")
    ap.add_argument("--out", required=True, help="output JSONL file path")
    ap.add_argument("--print", action="store_true", help="also print events to stdout")
    args = ap.parse_args()

    host = socket.gethostname()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)

    # Write a header marker event so downstream knows it started
    start_evt = {
        "ts": datetime.now().isoformat(),
        "host": host,
        "event": "monitor_start",
        "source": args.authlog,
    }
    jsonl_append(args.out, start_evt)
    if args.print:
        print(json.dumps(start_evt))

    for line in follow_file(args.authlog):
        event_type, fields = parse_line(line)
        if not event_type:
            continue

        evt = {
            "ts": datetime.now().isoformat(),
            "host": host,
            "event": event_type,
            "raw": line,
            **fields,
        }
        jsonl_append(args.out, evt)
        if args.print:
            print(json.dumps(evt))


if __name__ == "__main__":
    main()
