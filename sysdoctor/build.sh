#!/usr/bin/env bash
set -euo pipefail
command -v python3 >/dev/null || { echo "python3 not found" >&2; exit 1; }
python3 -m pip install --upgrade pyinstaller
python3 -m PyInstaller --onefile --console --clean --name sysdoctor sysdoctor.py
echo
echo "Done: dist/sysdoctor"
echo "Try:  ./dist/sysdoctor info"
