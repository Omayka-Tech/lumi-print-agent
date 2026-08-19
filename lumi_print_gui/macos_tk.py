"""pyenv en macOS a menudo queda ligado a Tcl/Tk 8.6; Homebrew ya sirve 9.x."""

from __future__ import annotations

import os
import sys
from typing import List, Optional


def tcl_tk8_lib_dirs() -> List[str]:
    dirs = []
    for prefix in ("/opt/homebrew/opt/tcl-tk@8", "/usr/local/opt/tcl-tk@8"):
        lib = os.path.join(prefix, "lib")
        if os.path.isfile(os.path.join(lib, "libtk8.6.dylib")):
            dirs.append(lib)
    return dirs


def tkinter_import_error() -> Optional[BaseException]:
    try:
        import tkinter  # noqa: F401
    except Exception as exc:
        return exc
    return None


def reexec_with_tcl_tk8(argv: List[str]) -> None:
    """Relanza el proceso con DYLD_FALLBACK_LIBRARY_PATH si hace falta Tcl/Tk 8.6."""
    if sys.platform != "darwin":
        return
    if os.environ.get("LUMI_PRINT_TK_READY") == "1":
        return
    from lumi_print_agent.paths import is_frozen

    if is_frozen():
        return
    err = tkinter_import_error()
    if err is None:
        return
    libs = tcl_tk8_lib_dirs()
    if not libs:
        return
    env = os.environ.copy()
    prev = env.get("DYLD_FALLBACK_LIBRARY_PATH", "")
    env["DYLD_FALLBACK_LIBRARY_PATH"] = libs[0] + ((":" + prev) if prev else "")
    env["LUMI_PRINT_TK_READY"] = "1"
    os.execvpe(sys.executable, [sys.executable, "-m", "lumi_print_gui"] + list(argv), env)
