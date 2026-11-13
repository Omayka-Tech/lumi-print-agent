"""Self-install a una ruta de usuario estable (sin privilegios de administrador)."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

from lumi_print_agent.paths import is_frozen, user_data_dir

# Keep user config/logs when refreshing the frozen tree.
_PRESERVE_NAMES = frozenset({"config.yaml", "config.yml", "logs"})


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


def _is_permission(exc: BaseException) -> bool:
    if isinstance(exc, PermissionError):
        return True
    if not isinstance(exc, OSError):
        return False
    winerror = getattr(exc, "winerror", None)
    # WinError 5 access denied, 32 sharing violation (DLL still mapped).
    return winerror in (5, 32) or exc.errno in (1, 13)


def _make_writable(path: Path) -> None:
    try:
        os.chmod(str(path), stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass


def _grant_user_acl(dest: Path) -> None:
    """Repair a tree left behind by an elevated 'Run as administrator' copy."""
    if sys.platform != "win32" or not dest.exists():
        return
    user = os.environ.get("USERNAME") or os.environ.get("USER")
    if not user:
        return
    try:
        subprocess.call(
            ["icacls", str(dest), "/grant", "{}:(OI)(CI)F".format(user), "/T", "/C"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return


def _rmtree(path: Path) -> None:
    def _onerror(func, failed, _exc_info):
        _make_writable(Path(failed))
        func(failed)

    shutil.rmtree(str(path), onerror=_onerror)


def _copy_file(src: Path, dest: Path) -> None:
    """Copy one file, replacing a DLL that Windows still has mapped.

    Closing the window only hides the tray, so ``libcrypto-1_1.dll`` stays
    locked. An elevated retry then fails with errno 13 for every later launch.
    Renaming the locked file aside works while the mapping is alive.
    """
    if dest.exists():
        _make_writable(dest)
    try:
        shutil.copy2(str(src), str(dest))
        return
    except OSError as exc:
        if not _is_permission(exc) or not dest.exists():
            raise
    _grant_user_acl(dest.parent)
    _make_writable(dest)
    stale = dest.with_name(dest.name + ".stale")
    if stale.exists():
        try:
            _make_writable(stale)
            stale.unlink()
        except OSError:
            stale = dest.with_name("{}.stale-{}".format(dest.name, os.getpid()))
    os.replace(str(dest), str(stale))
    shutil.copy2(str(src), str(dest))


def copy_into_user_dir() -> Path:
    """Copy the full PyInstaller onedir (exe + sibling DLLs + _internal).

    PyInstaller 5.x Win onedir keeps ``pythonXY.dll`` / VCRuntime next to the
    exe (not only under ``_internal``). Copying just the exe left AppData
    broken with ``Error loading Python DLL ... python37.dll``.
    """
    src_exe = Path(sys.executable).resolve()
    return copy_tree_into_user_dir(src_exe.parent, exe_name=src_exe.name)


def copy_tree_into_user_dir(src_dir: Path, exe_name: Optional[str] = None) -> Path:
    """Copia un árbol onedir (release o build local) a la carpeta de usuario."""
    dest = user_data_dir()
    dest.mkdir(parents=True, exist_ok=True)
    src_dir = Path(src_dir).resolve()
    if exe_name:
        target_exe = dest / exe_name
    else:
        candidates = sorted(src_dir.glob("LumiPrintAgent*"))
        exe = next((p for p in candidates if p.is_file()), None)
        if exe is None:
            raise FileNotFoundError("No hay ejecutable LumiPrintAgent en {}".format(src_dir))
        target_exe = dest / exe.name

    if src_dir == dest.resolve():
        return target_exe

    _grant_user_acl(dest)
    for item in src_dir.iterdir():
        name = item.name
        if name in _PRESERVE_NAMES:
            continue
        dest_item = dest / name
        if item.is_dir():
            if dest_item.exists():
                try:
                    _rmtree(dest_item)
                except OSError as exc:
                    if not _is_permission(exc):
                        raise
                    stale = dest_item.with_name(dest_item.name + ".stale")
                    if stale.exists():
                        _rmtree(stale)
                    os.replace(str(dest_item), str(stale))
            shutil.copytree(str(item), str(dest_item))
        else:
            _copy_file(item, dest_item)

    return target_exe


def relaunch_installed(extra_args: Optional[List[str]] = None) -> None:
    exe = installed_executable()
    args = extra_args if extra_args is not None else [a for a in sys.argv[1:] if a != "--install"]
    kwargs = {}
    if sys.platform == "win32":
        kwargs["close_fds"] = False
    subprocess.Popen([str(exe)] + args, cwd=str(exe.parent), **kwargs)


def _stop_other_instances() -> None:
    """End a previous tray process so its DLLs can be replaced."""
    if sys.platform != "win32":
        return
    exe_name = Path(sys.executable).name
    if not exe_name.lower().endswith(".exe"):
        return
    try:
        rc = subprocess.call(
            [
                "taskkill",
                "/F",
                "/FI",
                "IMAGENAME eq {}".format(exe_name),
                "/FI",
                "PID ne {}".format(os.getpid()),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return
    if rc == 0:
        time.sleep(0.6)


def _report_install_permission_error(dest: Path, exc: BaseException) -> None:
    message = (
        "No se pudo copiar el agente a:\n{}\n\n"
        "Windows negó el acceso ({}). Suele pasar si Lumi Print Agent sigue "
        "abierto en la bandeja, o si una ejecución como administrador dejó "
        "libcrypto-1_1.dll bloqueada.\n\n"
        "Salí del icono de la bandeja (o cerralo en el Administrador de tareas) "
        "y volvé a abrir LumiPrintAgent.exe."
    ).format(dest, exc)
    sys.stderr.write(message + "\n")
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, "Lumi Print Agent", 0x10)
    except Exception:
        return


def _prefer_running_agent() -> bool:
    """Focus a healthy agent we could not replace, instead of crashing the copy."""
    try:
        from lumi_print_agent.local_api import ask_existing_to_open, probe_running
    except Exception:
        return False
    if not probe_running():
        return False
    _stop_other_instances()
    if not probe_running():
        return False
    ask_existing_to_open()
    return True


def self_install_and_relaunch() -> int:
    if _prefer_running_agent():
        return 0
    try:
        copy_into_user_dir()
    except OSError as exc:
        if not _is_permission(exc):
            raise
        _stop_other_instances()
        _grant_user_acl(user_data_dir())
        try:
            copy_into_user_dir()
        except OSError as again:
            if not _is_permission(again):
                raise
            _report_install_permission_error(user_data_dir(), again)
            return 1
    try:
        from . import autostart

        autostart.enable()
    except Exception:
        pass
    relaunch_installed(extra_args=["--hidden"])
    return 0
