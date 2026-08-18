"""Punto de entrada PyInstaller (GUI por default; --headless para sucursal)."""

from __future__ import annotations

import sys

from lumi_print_gui.app import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
