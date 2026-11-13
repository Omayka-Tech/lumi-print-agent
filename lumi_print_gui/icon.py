"""Icono del faro Lumi para la bandeja y la ventana."""

from __future__ import annotations

import os
import sys
from typing import Any


def asset_path(name: str) -> str:
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, "lumi_print_gui", "assets", name)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", name)


def make_icon_image() -> Any:
    from PIL import Image

    for name in ("lumi-print-mark.png", "lumi-mark.png"):
        path = asset_path(name)
        if os.path.isfile(path):
            return Image.open(path).convert("RGBA")
    raise FileNotFoundError("No hay asset de icono en lumi_print_gui/assets")


def apply_window_icon(root: Any) -> None:
    ico = asset_path("lumi.ico")
    if not os.path.isfile(ico):
        ico = asset_path("favicon.ico")
    if not os.path.isfile(ico):
        return
    try:
        root.iconbitmap(default=ico)
    except Exception:
        try:
            root.iconbitmap(ico)
        except Exception:
            return
