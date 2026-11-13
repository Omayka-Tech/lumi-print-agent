"""Versión del agente (pyproject / VERSION / embebida)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Tuple


def current_version() -> str:
    try:
        from importlib import metadata

        return metadata.version("lumi-print-agent")
    except Exception:
        pass
    for candidate in _version_files():
        try:
            text = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            return text
    from lumi_print_agent import __version__

    return str(__version__ or "0.0.0")


def parse_version(value: str) -> Tuple[int, ...]:
    text = (value or "").strip().lstrip("vV")
    parts = []
    for chunk in text.split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts) if parts else (0,)


def is_newer(candidate: str, current: str) -> bool:
    return parse_version(candidate) > parse_version(current)


def _version_files():
    if getattr(sys, "frozen", False):
        yield Path(sys.executable).resolve().parent / "VERSION"
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            yield Path(meipass) / "VERSION"
    here = Path(__file__).resolve().parent.parent
    yield here / "VERSION"
    env = os.environ.get("LUMI_PRINT_AGENT_VERSION_FILE")
    if env:
        yield Path(env)
