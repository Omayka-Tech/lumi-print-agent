"""Icono simple generado en runtime (sin assets binarios)."""

from __future__ import annotations

from typing import Any


def make_icon_image() -> Any:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (64, 64), color=(18, 72, 140))
    draw = ImageDraw.Draw(img)
    draw.rectangle((6, 6, 57, 57), outline=(255, 255, 255), width=3)
    draw.rectangle((18, 22, 46, 48), outline=(255, 220, 80), width=3)
    draw.line((18, 30, 46, 30), fill=(255, 220, 80), width=2)
    return img
