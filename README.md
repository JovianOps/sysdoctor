# sysdoctor

[![Python](https://img.shields.io/badge/python-3.9%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/github/license/JovianOps/sysdoctor?color=blue)](LICENSE)
[![CI](https://github.com/JovianOps/sysdoctor/actions/workflows/ci.yml/badge.svg)](https://github.com/JovianOps/sysdoctor/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/sysdoctor?logo=python&logoColor=white)](https://pypi.org/project/sysdoctor/)
[![GitHub stars](https://img.shields.io/github/stars/JovianOps/sysdoctor?style=social)](https://github.com/JovianOps/sysdoctor)

**SysDoctor** is a cross-platform system diagnostics and safe cleanup tool — think `htop`
+ `du` + `nc` + `PATH` audit combined into a single zero-dependency CLI. Pure Python
standard library only. No npm, no apt, no Homebrew. Just `python sysdoctor.py` and you're
diagnosing.

## Quick start

```bash
python sysdoctor.py info      # OS, CPU, memory, uptime, Python
python sysdoctor.py disk      # disk usage with configurable warning threshold
python sysdoctor.py big /var  # top 20 largest files under a directory
python sysdoctor.py net       # DNS + TCP connectivity check
python sysdoctor.py path      # audit PATH for duplicates, missing, non-dirs
python sysdoctor.py clean     # dry-run temp file cleanup (use --apply to delete)
```

Run `sysdoctor --help` for all options.

## Commands

| Command | Description | Example |
|---|---|---|
| `info` | System summary — OS, kernel, hostname, CPU cores, load avg, memory, uptime | `sysdoctor info` |
| `disk [--warn PCT]` | Disk usage per volume. Exit code 1 if any volume is above `--warn`% | `sysdoctor disk --warn 85` |
| `big PATH [-n N]` | Largest regular files under a directory (uses a heap, not sorted walk) | `sysdoctor big ~/Downloads -n 10` |
| `net` | DNS resolution of `example.com` + TCP connect to 1.1.1.1:443 and 8.8.8.8:53 | `sysdoctor net` |
| `path` | Audit your `PATH` variable — duplicates, missing dirs, non-directory entries | `sysdoctor path` |
| `clean [--days N] [--apply]` | Remove temp files older than N days (dry-run unless `--apply`) | `sysdoctor clean --days 3 --apply` |

## Screenshots

```
$ sysdoctor info
OS        : Windows 11 10.0.22631 (AMD64)
Machine   : AMD64  Host: DESKTOP-ABC123
CPU cores : 16
Memory    : 2.1 GiB used of 16.0 GiB (13%)
Uptime    : 1d 4h 22m
Python    : 3.14.7 (C:\tools\python.exe)
```

```
$ sysdoctor disk --warn 80
Volume                       Used       Total      Use%
C:\                         128.3 GiB    476.3 GiB    27%
D:\                          12.1 GiB    931.5 GiB     1%
```

```
$ sysdoctor path
18 PATH entries checked, 2 problem(s) found
MISSING   : C:\Program Files\nodejs\
DUPLICATE : C:\Windows\System32
```

```
$ sysdoctor clean --days 3
DRY RUN (use --apply to delete): files older than 3 day(s)

[C:\Users\jovian\AppData\Local\Temp]
Would remove 42 file(s), 256.0 MiB
```

## Features

- **Zero dependencies** — only Python 3.9+ standard library. Works on Windows and Linux.
- **Safe by default** — `clean` is a dry run unless you pass `--apply`. No destructive
  operation runs without explicit opt-in.
- **Non-crashing probes** — platform probes catch all exceptions. If memory or uptime
  can't be read, you get `unavailable`, not a traceback.
- **Executable builds** — PyInstaller one-file builds for Windows (`.exe`) and Linux
  (ELF). See `build.bat` / `build.sh`.

## Build standalone executable

```bash
# Windows
build.bat        # -> dist\sysdoctor.exe

# Linux
./build.sh       # -> dist/sysdoctor
```

> Unsigned executables are occasionally flagged by Windows SmartScreen or antivirus —
> this is a known false positive.

## Testing

```bash
pip install pytest
python -m pytest tests/ -v
```

## Contributing

Bug reports, feature ideas, and PRs are welcome!

1. Fork the repo
2. Create a branch: `git checkout -b fix/your-fix`
3. Make your changes
4. Run tests: `python -m pytest tests/ -v`
5. Submit a PR

## License

MIT — see [LICENSE](LICENSE).
