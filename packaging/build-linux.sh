#!/usr/bin/env bash
# Build portable onedir for Linux (Python 3.10+).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 -m pip install -e ".[gui,packaging]"
python3 -m PyInstaller --noconfirm --clean packaging/lumi-print-agent.spec
echo "OK: ${ROOT}/dist/LumiPrintAgent"
echo "Primer arranque copia a ~/.local/share/lumi/print-agent/"
