"""Autostart a nivel usuario (sin admin): HKCU / LaunchAgent / .desktop."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List, Optional

from lumi_print_agent.paths import current_app_dir, is_frozen, user_data_dir

RUN_VALUE_NAME = "LumiPrintAgent"
LAUNCH_LABEL = "tech.omayka.lumi-print-agent"
DESKTOP_NAME = "lumi-print-agent.desktop"


def launch_command() -> List[str]:
    # Autostart: solo bandeja (cerca del reloj), sin abrir la ventana.
    if is_frozen():
        return [str(Path(sys.executable).resolve()), "--hidden"]
    repo = current_app_dir()
    return [str(Path(sys.executable).resolve()), "-m", "lumi_print_gui", "--hidden"]


def _launch_env() -> dict:
    env = {}
    if not is_frozen():
        env["PYTHONPATH"] = str(current_app_dir())
    return env


def is_installed_copy() -> bool:
    if not is_frozen():
        return True
    try:
        return Path(sys.executable).resolve().parent == user_data_dir().resolve()
    except OSError:
        return False


def _win_run_key_set(command: str) -> None:
    import winreg

    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0,
        winreg.KEY_SET_VALUE,
    )
    try:
        winreg.SetValueEx(key, RUN_VALUE_NAME, 0, winreg.REG_SZ, command)
    finally:
        winreg.CloseKey(key)


def _win_run_key_delete() -> None:
    import winreg

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        )
    except OSError:
        return
    try:
        try:
            winreg.DeleteValue(key, RUN_VALUE_NAME)
        except FileNotFoundError:
            pass
        except OSError:
            pass
    finally:
        winreg.CloseKey(key)


def _win_run_key_get() -> Optional[str]:
    import winreg

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_READ,
        )
    except OSError:
        return None
    try:
        value, _typ = winreg.QueryValueEx(key, RUN_VALUE_NAME)
        return str(value)
    except OSError:
        return None
    finally:
        winreg.CloseKey(key)


def macos_plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / "{}.plist".format(LAUNCH_LABEL)


def linux_desktop_path() -> Path:
    config_home = os.environ.get("XDG_CONFIG_HOME")
    base = Path(config_home) if config_home else Path.home() / ".config"
    return base / "autostart" / DESKTOP_NAME


def _plist_body(cmd: List[str]) -> str:
    args = "".join("    <string>{}</string>\n".format(_xml_escape(a)) for a in cmd)
    env_xml = ""
    extra = _launch_env()
    if extra:
        entries = []
        for key, val in extra.items():
            entries.append(
                "      <key>{}</key>\n      <string>{}</string>".format(
                    _xml_escape(key), _xml_escape(val)
                )
            )
        env_xml = "  <key>EnvironmentVariables</key>\n  <dict>\n{}\n  </dict>\n".format(
            "\n".join(entries)
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        "<dict>\n"
        "  <key>Label</key>\n"
        "  <string>{}</string>\n"
        "  <key>ProgramArguments</key>\n"
        "  <array>\n{}"
        "  </array>\n"
        "{}"
        "  <key>RunAtLoad</key>\n"
        "  <true/>\n"
        "  <key>KeepAlive</key>\n"
        "  <false/>\n"
        "</dict>\n"
        "</plist>\n"
    ).format(LAUNCH_LABEL, args, env_xml)


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _desktop_body(cmd: List[str]) -> str:
    exec_line = " ".join(_quote(part) for part in cmd)
    extra = _launch_env()
    env_prefix = ""
    if extra:
        env_prefix = "env " + " ".join("{}={}".format(k, _quote(v)) for k, v in extra.items()) + " "
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Version=1.0\n"
        "Name=Lumi Print Agent\n"
        "Comment=Agente local de impresión Lumi\n"
        "Exec={}{}\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
        "Hidden=false\n"
    ).format(env_prefix, exec_line)


def _quote(value: str) -> str:
    if not value or any(ch.isspace() for ch in value) or '"' in value:
        return '"' + value.replace('"', '\\"') + '"'
    return value


def enable() -> None:
    cmd = launch_command()
    if sys.platform == "win32":
        quoted = " ".join(_quote(part) for part in cmd)
        _win_run_key_set(quoted)
        return
    if sys.platform == "darwin":
        path = macos_plist_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_plist_body(cmd), encoding="utf-8")
        return
    path = linux_desktop_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_desktop_body(cmd), encoding="utf-8")


def disable() -> None:
    if sys.platform == "win32":
        _win_run_key_delete()
        return
    if sys.platform == "darwin":
        path = macos_plist_path()
        if path.is_file():
            path.unlink()
        return
    path = linux_desktop_path()
    if path.is_file():
        path.unlink()


def is_enabled() -> bool:
    if sys.platform == "win32":
        return bool(_win_run_key_get())
    if sys.platform == "darwin":
        return macos_plist_path().is_file()
    return linux_desktop_path().is_file()
