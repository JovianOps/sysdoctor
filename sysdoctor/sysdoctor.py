#!/usr/bin/env python3
"""sysdoctor - cross-platform (Windows/Linux) system diagnostics and safe cleanup.

Commands:
    info                  OS, CPU, memory, uptime, Python version
    disk [--warn PCT]     Disk usage per volume (exit code 1 if above threshold)
    big PATH [-n N]       Largest files under PATH
    net                   DNS + TCP connectivity check
    path                  Detect duplicate / missing / non-directory PATH entries
    clean [--days D] [--apply]
                          Remove old temp files (dry-run unless --apply)

Only the Python standard library is used.
"""
from __future__ import annotations

import argparse
import ctypes
import heapq
import logging
import os
import platform
import shutil
import socket
import string
import sys
import tempfile
import time
from pathlib import Path
from typing import Iterator, Optional

LOG = logging.getLogger("sysdoctor")
IS_WINDOWS = os.name == "nt"

PSEUDO_FS = {
    "proc", "sysfs", "devtmpfs", "devpts", "tmpfs", "cgroup", "cgroup2",
    "securityfs", "debugfs", "tracefs", "configfs", "fusectl", "pstore",
    "bpf", "mqueue", "hugetlbfs", "autofs", "binfmt_misc", "overlay",
    "squashfs", "nsfs", "ramfs", "efivarfs",
}


def human_size(num_bytes: float) -> str:
    """Format a byte count as a human-readable string."""
    value = float(num_bytes)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(value) < 1024.0:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024.0
    return f"{value:.1f} PiB"


def human_duration(seconds: float) -> str:
    """Format seconds as 'Xd Yh Zm'."""
    total = int(seconds)
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    return f"{days}d {hours}h {minutes}m"


# --------------------------------------------------------------------------- #
# Platform probes
# --------------------------------------------------------------------------- #
def get_memory() -> Optional[tuple[int, int]]:
    """Return (total_bytes, available_bytes) or None if unavailable."""
    try:
        if IS_WINDOWS:
            class MemoryStatusEx(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatusEx()
            status.dwLength = ctypes.sizeof(MemoryStatusEx)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # type: ignore[attr-defined]
                raise OSError("GlobalMemoryStatusEx failed")
            return int(status.ullTotalPhys), int(status.ullAvailPhys)

        fields: dict[str, int] = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            for line in handle:
                key, _, rest = line.partition(":")
                parts = rest.split()
                if parts and parts[0].isdigit():
                    fields[key] = int(parts[0]) * 1024
        total = fields.get("MemTotal")
        available = fields.get("MemAvailable", fields.get("MemFree"))
        if total is None or available is None:
            raise ValueError("MemTotal/MemAvailable missing in /proc/meminfo")
        return total, available
    except Exception as exc:  # noqa: BLE001 - diagnostics must never crash
        LOG.debug("memory probe failed: %s", exc)
        return None


def get_uptime_seconds() -> Optional[float]:
    """Return system uptime in seconds or None if unavailable."""
    try:
        if IS_WINDOWS:
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            kernel32.GetTickCount64.restype = ctypes.c_ulonglong
            return kernel32.GetTickCount64() / 1000.0
        with open("/proc/uptime", "r", encoding="utf-8") as handle:
            return float(handle.read().split()[0])
    except Exception as exc:  # noqa: BLE001
        LOG.debug("uptime probe failed: %s", exc)
        return None


def list_volumes() -> list[str]:
    """Return mount points (Linux) or drive roots (Windows) worth reporting."""
    volumes: list[str] = []
    try:
        if IS_WINDOWS:
            for letter in string.ascii_uppercase:
                root = f"{letter}:\\"
                if os.path.exists(root):
                    volumes.append(root)
        else:
            seen: set[str] = set()
            with open("/proc/mounts", "r", encoding="utf-8") as handle:
                for line in handle:
                    parts = line.split()
                    if len(parts) < 3:
                        continue
                    mount = parts[1].replace("\\040", " ")
                    fstype = parts[2]
                    if fstype in PSEUDO_FS or mount in seen:
                        continue
                    if mount.startswith(("/proc", "/sys", "/dev", "/run", "/snap")):
                        continue
                    seen.add(mount)
                    volumes.append(mount)
    except Exception as exc:  # noqa: BLE001
        LOG.debug("volume enumeration failed: %s", exc)
    if not volumes:
        volumes.append(os.path.abspath(os.sep))
    return volumes


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def cmd_info(_: argparse.Namespace) -> int:
    uname = platform.uname()
    print(f"OS        : {uname.system} {uname.release} ({platform.version()})")
    print(f"Machine   : {uname.machine}  Host: {uname.node}")
    print(f"CPU cores : {os.cpu_count() or 'unknown'}")
    if hasattr(os, "getloadavg"):
        try:
            one, five, fifteen = os.getloadavg()
            print(f"Load avg  : {one:.2f} {five:.2f} {fifteen:.2f}")
        except OSError as exc:
            LOG.debug("loadavg failed: %s", exc)
    mem = get_memory()
    if mem:
        total, avail = mem
        used_pct = (total - avail) / total * 100 if total else 0.0
        print(f"Memory    : {human_size(total - avail)} used of {human_size(total)} ({used_pct:.0f}%)")
    else:
        print("Memory    : unavailable")
    uptime = get_uptime_seconds()
    print(f"Uptime    : {human_duration(uptime) if uptime is not None else 'unavailable'}")
    print(f"Python    : {platform.python_version()} ({sys.executable})")
    return 0


def cmd_disk(args: argparse.Namespace) -> int:
    exceeded = False
    print(f"{'Volume':<28}{'Used':>12}{'Total':>12}{'Use%':>7}")
    for volume in list_volumes():
        try:
            usage = shutil.disk_usage(volume)
        except OSError as exc:
            LOG.warning("cannot read %s: %s", volume, exc)
            continue
        pct = usage.used / usage.total * 100 if usage.total else 0.0
        flag = ""
        if pct >= args.warn:
            flag = "  <-- WARNING"
            exceeded = True
        print(f"{volume:<28}{human_size(usage.used):>12}{human_size(usage.total):>12}{pct:>6.0f}%{flag}")
    return 1 if exceeded else 0


def iter_files(root: Path) -> Iterator[tuple[Path, os.stat_result]]:
    """Yield regular files below root without following symlinks; skip unreadable entries."""

    def on_error(err: OSError) -> None:
        LOG.debug("skipping %s: %s", getattr(err, "filename", "?"), err)

    for dirpath, _dirs, files in os.walk(root, topdown=True, onerror=on_error, followlinks=False):
        for name in files:
            path = Path(dirpath) / name
            try:
                info = path.lstat()
            except OSError as exc:
                LOG.debug("stat failed for %s: %s", path, exc)
                continue
            if path.is_symlink():
                continue
            yield path, info


def cmd_big(args: argparse.Namespace) -> int:
    root = Path(args.path).expanduser()
    if not root.is_dir():
        LOG.error("not a directory: %s", root)
        return 2
    if args.n < 1:
        LOG.error("-n must be >= 1")
        return 2
    heap: list[tuple[int, str]] = []
    scanned = 0
    for path, info in iter_files(root):
        scanned += 1
        item = (info.st_size, str(path))
        if len(heap) < args.n:
            heapq.heappush(heap, item)
        elif item > heap[0]:
            heapq.heapreplace(heap, item)
    print(f"Scanned {scanned} files under {root}")
    for size, path in sorted(heap, reverse=True):
        print(f"{human_size(size):>12}  {path}")
    return 0


def cmd_net(_: argparse.Namespace) -> int:
    ok = True
    try:
        addrs = {item[4][0] for item in socket.getaddrinfo("example.com", 443, proto=socket.IPPROTO_TCP)}
        print(f"DNS       : OK ({', '.join(sorted(addrs))})")
    except OSError as exc:
        print(f"DNS       : FAIL ({exc})")
        ok = False
    for host, port in (("1.1.1.1", 443), ("8.8.8.8", 53)):
        start = time.monotonic()
        try:
            with socket.create_connection((host, port), timeout=3):
                print(f"TCP {host}:{port:<4}: OK ({(time.monotonic() - start) * 1000:.0f} ms)")
        except OSError as exc:
            print(f"TCP {host}:{port:<4}: FAIL ({exc})")
            ok = False
    return 0 if ok else 1


def cmd_path(_: argparse.Namespace) -> int:
    raw = os.environ.get("PATH", "")
    entries = [e for e in raw.split(os.pathsep) if e]
    seen: set[str] = set()
    problems = 0
    for entry in entries:
        key = os.path.normcase(os.path.normpath(entry))
        expanded = os.path.expandvars(entry)
        if key in seen:
            print(f"DUPLICATE : {entry}")
            problems += 1
        seen.add(key)
        if not os.path.exists(expanded):
            print(f"MISSING   : {entry}")
            problems += 1
        elif not os.path.isdir(expanded):
            print(f"NOT A DIR : {entry}")
            problems += 1
    print(f"{len(entries)} PATH entries checked, {problems} problem(s) found")
    return 1 if problems else 0


def temp_targets() -> list[Path]:
    targets = [Path(tempfile.gettempdir())]
    home = Path.home()
    if not IS_WINDOWS:
        targets.append(home / ".cache" / "thumbnails")
    return [t for t in targets if t.is_dir()]


def cmd_clean(args: argparse.Namespace) -> int:
    if args.days < 1:
        LOG.error("--days must be >= 1")
        return 2
    cutoff = time.time() - args.days * 86400
    total_bytes = 0
    total_files = 0
    failures = 0
    mode = "DELETING" if args.apply else "DRY RUN (use --apply to delete)"
    print(f"{mode}: files older than {args.days} day(s)")
    for target in temp_targets():
        print(f"\n[{target}]")
        for path, info in iter_files(target):
            if info.st_mtime >= cutoff:
                continue
            total_files += 1
            total_bytes += info.st_size
            if not args.apply:
                LOG.debug("would remove %s", path)
                continue
            try:
                path.unlink()
            except OSError as exc:  # in-use files are common on Windows
                failures += 1
                total_files -= 1
                total_bytes -= info.st_size
                LOG.debug("could not remove %s: %s", path, exc)
    verb = "Removed" if args.apply else "Would remove"
    print(f"\n{verb} {total_files} file(s), {human_size(total_bytes)}")
    if failures:
        print(f"{failures} file(s) skipped (in use or permission denied)")
    return 0


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sysdoctor", description=__doc__.splitlines()[0])
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("info", help="system summary").set_defaults(func=cmd_info)

    p_disk = sub.add_parser("disk", help="disk usage per volume")
    p_disk.add_argument("--warn", type=float, default=90.0, help="warn at this percent used (default 90)")
    p_disk.set_defaults(func=cmd_disk)

    p_big = sub.add_parser("big", help="largest files under a directory")
    p_big.add_argument("path", help="directory to scan")
    p_big.add_argument("-n", type=int, default=20, help="number of files to show (default 20)")
    p_big.set_defaults(func=cmd_big)

    sub.add_parser("net", help="connectivity check").set_defaults(func=cmd_net)
    sub.add_parser("path", help="audit the PATH variable").set_defaults(func=cmd_path)

    p_clean = sub.add_parser("clean", help="remove old temp files (dry-run by default)")
    p_clean.add_argument("--days", type=int, default=7, help="minimum file age in days (default 7)")
    p_clean.add_argument("--apply", action="store_true", help="actually delete files")
    p_clean.set_defaults(func=cmd_clean)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        return 130
    except Exception:  # noqa: BLE001
        LOG.exception("unexpected error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
