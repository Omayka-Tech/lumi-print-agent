# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: onedir portable (Win7 / macOS / Linux)."""

import os
import sys

from PyInstaller.utils.hooks import collect_submodules

spec_root = os.path.dirname(os.path.abspath(SPEC))
repo = os.path.dirname(spec_root)

hidden = collect_submodules("lumi_print_agent") + collect_submodules("lumi_print_gui")
hidden += [
    "PIL",
    "PIL.Image",
    "PIL.ImageDraw",
    "yaml",
    "requests",
    "pystray",
]

if sys.platform == "win32":
    hidden.append("pystray._win32")
elif sys.platform == "darwin":
    hidden.append("pystray._darwin")
else:
    hidden.append("pystray._util.gtk")

a = Analysis(
    [os.path.join(spec_root, "entry.py")],
    pathex=[repo],
    binaries=[],
    datas=[],
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LumiPrintAgent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="LumiPrintAgent",
)
