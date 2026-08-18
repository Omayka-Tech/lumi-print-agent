"""Self-install a una ruta de usuario estable (sin privilegios de administrador)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from lumi_print_agent.paths import is_frozen, user_data_dir


def needs_self_install() -> bool:
    if os.environ.get("LUMI_PRINT_PORTABLE") == "1":
        return False
    if "--portable" in sys.argv:
        return False
    if not is_frozen():
        return False
    try:
        return Path(sys.executable).resolve().parent != user_data_dir().resolve()
    except OSError:
        return True


def installed_executable() -> Path:
    dest = user_data_dir()
    return dest / Path(sys.executable).name


def copy_into_user_dir() -> Path:
    dest = user_data_dir()
    dest.mkdir(parents=True, exist_ok=True)
    src_exe = Path(sys.executable).resolve()
    src_dir = src_exe.parent
    target_exe = dest / src_exe.name
    if src_exe != target_exe:
        shutil.copy2(str(src_exe), str(target_exe))
    internal = src_dir / "_internal"
    if internal.is_dir():
        dest_internal = dest / "_internal"
        if dest_internal.exists() and dest_internal.resolve() != internal.resolve():
            shutil.rmtree(str(dest_internal))
        if not dest_internal.exists():
            shutil.copytree(str(internal), str(dest_internal))
    return target_exe


def relaunch_installed(extra_args: Optional[List[str]] = None) -> None:
    exe = installed_executable()
    args = extra_args if extra_args is not None else [a for a in sys.argv[1:] if a != "--install"]
    kwargs = {}
    if sys.platform == "win32":
        kwargs["close_fds"] = False
    subprocess.Popen([str(exe)] + args, cwd=str(exe.parent), **kwargs)


def self_install_and_relaunch() -> int:
    copy_into_user_dir()
    relaunch_installed()
    return 0
