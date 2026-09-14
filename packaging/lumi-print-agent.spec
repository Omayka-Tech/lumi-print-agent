# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: onedir portable (Win7 / macOS / Linux).

Windows frozen builds MUST use CPython 3.7.x for virgin Win7 SP1 hosts.
Python 3.8+ needs KB2533623/KB3063858 (SetDefaultDllDirectories) or
``_socket`` fails with \"parameter is incorrect\" during import.
"""

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

# Agent does not use multiprocessing; excluding avoids pyi_rth_multiprocessing
# which eagerly imports socket and surfaces Win7 DLL failures before our UI.
excludes = [
    "multiprocessing",
    "multiprocessing.spawn",
    "multiprocessing.popen_spawn_win32",
    "concurrent.futures.process",
]

a = Analysis(
    [os.path.join(spec_root, "entry.py")],
    pathex=[repo],
    binaries=[],
    datas=[],
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
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
