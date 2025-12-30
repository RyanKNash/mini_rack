#!/usr/bin/env python3
"""
collector.py
Pull (collect) JSONL log files from multiple nodes over SSH and append locally.

Why this design:
- Pull-based (logger initiates), so targets don't need to push outward.
- Uses ssh + sftp; no extra Python deps.
- Maintains a per-source "offset" so it only fetches new bytes.
- Handles truncation/rotation by resetting offset safely.

Requirements:
- SSH key auth from logger -> targets (recommended).
- Remote user must have read access to the file (or use sudo on remote + a root-readable copy).

Usage:
  python3 collector.py --config ./collector_config.json --outdir ./telemetry --interval 15

Example config JSON:
{
  "sources": [
    {
      "name": "smart_house_pi3",
      "host": "192.168.1.50",
      "port": 22,
      "user": "pi",
      "remote_path": "/var/log/iot_auth_events.jsonl"
    }
  ]
}
"""

import argparse
import json
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class Source:
    name: str
    host: str
    user: str
    remote_path: str
    port: int = 22


def iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def run(cmd: List[str], timeout: int = 20) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, obj: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
    os.replace(tmp, path)


def ssh_base_args(src: Source) -> List[str]:
    return [
        "ssh",
        "-p",
        str(src.port),
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=8",
        f"{src.user}@{src.host}",
    ]


def sftp_base_args(src: Source) -> List[str]:
    return [
        "sftp",
        "-P",
        str(src.port),
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=8",
        f"{src.user}@{src.host}",
    ]


def remote_stat_size(src: Source) -> Optional[int]:
    """
    Get remote file size via `stat -c %s`.
    Returns None if unreachable or file missing.
    """
    cmd = ssh_base_args(src) + ["bash", "-lc", f"stat -c %s {sh_quote(src.remote_path)} 2>/dev/null"]
    p = run(cmd)
    if p.returncode != 0:
        return None
    out = p.stdout.strip()
    if not out.isdigit():
        return None
    return int(out)


def sh_quote(s: str) -> str:
    # minimal shell quoting
    return "'" + s.replace("'", "'\"'\"'") + "'"


def sftp_read_range(src: Source, offset: int, local_tmp: str) -> bool:
    """
    Use SFTP to read remote file starting at offset and write to local_tmp.
    Uses sftp 'get -a -p -R' if supported? Not consistently.
    So we do: 'get -p remote local' but we need offset. SFTP doesn't standardize ranged reads.

    Workaround:
    Use ssh to run `tail -c +<offset+1>` and capture stdout to local file.
    This avoids dependencies and is reliable.
    """
    # Implemented using ssh + tail for range read:
    start = offset + 1  # tail -c +N is 1-based
    cmd = ssh_base_args(src) + ["bash", "-lc", f"tail -c +{start} {sh_quote(src.remote_path)} 2>/dev/null || true"]
    p = run(cmd, timeout=30)
    if p.returncode != 0:
        return False
    with open(local_tmp, "wb") as f:
        f.write(p.stdout.encode("utf-8", errors="replace"))
    return True


def append_file(dst_path: str, src_path: str) -> int:
    """
    Append src_path bytes to dst_path. Returns bytes appended.
    """
    appended = 0
    with open(src_path, "rb") as src, open(dst_path, "ab") as dst:
        chunk = src.read(1024 * 256)
        while chunk:
            dst.write(chunk)
            appended += len(chunk)
            chunk = src.read(1024 * 256)
    return appended


def log_status(outdir: str, record: dict) -> None:
    path = os.path.join(outdir, "collector_status.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def load_sources(cfg_path: str) -> List[Source]:
    cfg = load_json(cfg_path)
    sources = []
    for s in cfg.get("sources", []):
        sources.append(
            Source(
                name=s["name"],
                host=s["host"],
                user=s["user"],
                remote_path=s["remote_path"],
                port=int(s.get("port", 22)),
            )
        )
    return sources


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="path to collector_config.json")
    ap.add_argument("--outdir", default="./telemetry", help="output directory")
    ap.add_argument("--interval", type=int, default=15, help="seconds between collection cycles")
    ap.add_argument("--once", action="store_true", help="run one cycle and exit")
    args = ap.parse_args()

    ensure_dir(args.outdir)

    offsets_path = os.path.join(args.outdir, "collector_offsets.json")
    offsets: Dict[str, int] = {}
    if os.path.exists(offsets_path):
        try:
            offsets = load_json(offsets_path)
        except Exception:
            offsets = {}

    sources = load_sources(args.config)
    if not sources:
        raise SystemExit("No sources found in config.")

    print(f"[{iso_now()}] collector starting. sources={len(sources)} outdir={args.outdir}")

    while True:
        for src in sources:
            key = f"{src.name}"
            local_out = os.path.join(args.outdir, f"{src.name}.jsonl")
            local_tmp = os.path.join(args.outdir, f".{src.name}.tmp")

            old_offset = int(offsets.get(key, 0))

            size = remote_stat_size(src)
            if size is None:
                rec = {
                    "ts": iso_now(),
                    "source": src.name,
                    "host": src.host,
                    "status": "unreachable_or_missing",
                    "detail": f"Could not stat {src.remote_path}",
                }
                log_status(args.outdir, rec)
                print(f"[{rec['ts']}] {src.name}: stat failed")
                continue

            # If remote file shrank, likely rotated/truncated -> reset offset
            if size < old_offset:
                old_offset = 0

            # Nothing new
            if size == old_offset:
                rec = {
                    "ts": iso_now(),
                    "source": src.name,
                    "host": src.host,
                    "status": "no_change",
                    "bytes_remote": size,
                }
                log_status(args.outdir, rec)
                continue

            # Fetch from old_offset to end
            ok = sftp_read_range(src, old_offset, local_tmp)
            if not ok:
                rec = {
                    "ts": iso_now(),
                    "source": src.name,
                    "host": src.host,
                    "status": "fetch_failed",
                    "bytes_remote": size,
                    "offset": old_offset,
                }
                log_status(args.outdir, rec)
                print(f"[{rec['ts']}] {src.name}: fetch failed")
                continue

            bytes_appended = append_file(local_out, local_tmp)
            try:
                os.remove(local_tmp)
            except Exception:
                pass

            # Update offset based on remote size (authoritative)
            offsets[key] = size
            save_json(offsets_path, offsets)

            rec = {
                "ts": iso_now(),
                "source": src.name,
                "host": src.host,
                "status": "ok",
                "bytes_appended": bytes_appended,
                "new_offset": size,
                "remote_path": src.remote_path,
            }
            log_status(args.outdir, rec)
            print(f"[{rec['ts']}] {src.name}: +{bytes_appended} bytes (offset {size})")

        if args.once:
            break
        time.sleep(args.interval)

    print(f"[{iso_now()}] collector finished.")


if __name__ == "__main__":
    main()
