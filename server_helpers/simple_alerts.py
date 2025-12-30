#!/usr/bin/env python3
"""
simple_alerts.py
Consumes JSONL events (from auth_log_monitor.py) and triggers basic alerts.

Alerts:
- N ssh_failed events from same IP in a time window
- ssh_accepted from an IP that recently had failures (possible password spray success)
- sudo usage (optional alert)

Usage:
  python3 simple_alerts.py --in ./iot_auth_events.jsonl --out ./alerts.jsonl

Notes:
- This tails the file (like tail -F) and keeps a small in-memory window.
- No external dependencies.
"""

import argparse
import json
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta


def now_dt():
    return datetime.now()


def jsonl_append(path: str, obj: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj) + "\n")


def follow_file(path: str):
    """Tail a file and yield newly appended lines; reopen on rotation."""
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
                f.seek(0, os.SEEK_END)  # follow new events only
                current_inode = inode(path)
            except FileNotFoundError:
                time.sleep(1)
                continue

        line = f.readline()
        if line:
            yield line.strip()
        else:
            new_inode = inode(path)
            if new_inode is not None and current_inode is not None and new_inode != current_inode:
                try:
                    f.close()
                except Exception:
                    pass
                f = None
            time.sleep(0.2)


def parse_ts(ts: str):
    # events are ISO format written by our monitor script
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True, help="input JSONL file")
    ap.add_argument("--out", dest="out_path", required=True, help="output alerts JSONL file")
    ap.add_argument("--fail-threshold", type=int, default=8, help="failures from same IP to alert")
    ap.add_argument("--window-min", type=int, default=5, help="time window minutes")
    ap.add_argument("--alert-sudo", action="store_true", help="alert on sudo usage")
    args = ap.parse_args()

    window = timedelta(minutes=args.window_min)

    # Track failures by IP (deque of timestamps)
    fails_by_ip: dict[str, deque] = defaultdict(deque)

    # Track last failure window by IP to correlate with a later success
    recent_fail_ips: dict[str, datetime] = {}

    print(f"Watching: {args.in_path}")
    print(f"Alerts -> {args.out_path}")
    print(f"Rule: {args.fail_threshold}+ failures/IP within {args.window_min} min")

    for line in follow_file(args.in_path):
        if not line:
            continue

        try:
            evt = json.loads(line)
        except Exception:
            continue

        ts = parse_ts(evt.get("ts", ""))
        if ts is None:
            ts = now_dt()

        ev = evt.get("event")
        ip = evt.get("ip")

        # Clean old entries periodically (light cleanup)
        cutoff = ts - window

        if ev == "ssh_failed" and ip:
            dq = fails_by_ip[ip]
            dq.append(ts)

            while dq and dq[0] < cutoff:
                dq.popleft()

            # mark IP as "recent failure"
            recent_fail_ips[ip] = ts

            if len(dq) == args.fail_threshold:
                alert = {
                    "ts": now_dt().isoformat(),
                    "alert": "ssh_bruteforce_suspected",
                    "ip": ip,
                    "count": len(dq),
                    "window_minutes": args.window_min,
                    "source_event": evt,
                }
                print(json.dumps(alert))
                jsonl_append(args.out_path, alert)

        elif ev == "ssh_accepted" and ip:
            # correlate: did this IP recently fail?
            last_fail = recent_fail_ips.get(ip)
            if last_fail and (ts - last_fail) <= window:
                alert = {
                    "ts": now_dt().isoformat(),
                    "alert": "ssh_success_after_failures",
                    "ip": ip,
                    "last_fail_ts": last_fail.isoformat(),
                    "window_minutes": args.window_min,
                    "source_event": evt,
                }
                print(json.dumps(alert))
                jsonl_append(args.out_path, alert)

        elif ev == "sudo" and args.alert_sudo:
            alert = {
                "ts": now_dt().isoformat(),
                "alert": "sudo_used",
                "user": evt.get("user"),
                "cmd": evt.get("cmd"),
                "source_event": evt,
            }
            print(json.dumps(alert))
            jsonl_append(args.out_path, alert)

        # Expire old recent_fail_ips entries
        # (keep map from growing forever)
        for rip, rts in list(recent_fail_ips.items()):
            if rts < cutoff:
                del recent_fail_ips[rip]


if __name__ == "__main__":
    main()
