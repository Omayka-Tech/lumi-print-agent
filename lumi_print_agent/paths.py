"""Rutas de usuario (AppData / Application Support / XDG)."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def user_data_dir() -> Path:
    """Directorio estable del agente (self-install + config.yaml)."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "Lumi" / "print-agent"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Lumi" / "print-agent"
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "lumi" / "print-agent"
    return Path.home() / ".local" / "share" / "lumi" / "print-agent"


def default_config_path() -> Path:
    env = os.environ.get("LUMI_PRINT_AGENT_CONFIG")
    if env:
        return Path(env)
    return user_data_dir() / "config.yaml"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def current_executable() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve()
    return Path(sys.executable).resolve()


def current_app_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]
