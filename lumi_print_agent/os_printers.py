"""Listado de impresoras del sistema (CUPS) y red local."""

from __future__ import annotations

import re
import subprocess
from typing import Any, Dict, List, Optional

from .discover import scan_subnet

_LPSTAT_PRINTER_RE = re.compile(r"^printer\s+(\S+)")


def _run_lpstat(*args: str) -> Optional[str]:
    try:
        result = subprocess.run(["lpstat", *args], capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return ""
    return result.stdout or ""


def _default_cups_queue() -> Optional[str]:
    out = _run_lpstat("-d")
    if out is None:
        return None
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("system default destination:"):
            return line.split(":", 1)[1].strip() or None
        if line.startswith("no system default"):
            return None
    return None


def list_cups_printers() -> List[Dict[str, Any]]:
    out = _run_lpstat("-p")
    if out is None:
        return []
    default_queue = _default_cups_queue()
    printers: List[Dict[str, Any]] = []
    for line in out.splitlines():
        match = _LPSTAT_PRINTER_RE.match(line.strip())
        if not match:
            continue
        queue = match.group(1)
        printers.append(
            {
                "id": "cups-{}".format(queue),
                "name": queue,
                "driver": "cups_spooler",
                "connection_mode": "os_spooler",
                "connection_detail": {"queue": queue},
                "is_default": queue == default_queue,
                "source": "cups",
                "printer_type": "laser_inkjet",
            }
        )
    return printers


def _network_printers(cidr: str) -> List[Dict[str, Any]]:
    devices: List[Dict[str, Any]] = []
    for item in scan_subnet(cidr):
        host = item["host"]
        port = int(item.get("port") or 9100)
        devices.append(
            {
                "id": "net-{}-{}".format(host, port),
                "name": "{}:{}".format(host, port),
                "driver": item.get("driver") or "escpos_network",
                "connection_mode": "network",
                "connection_detail": {"host": host, "port": port},
                "is_default": False,
                "source": "network",
                "printer_type": item.get("printer_type") or "thermal",
            }
        )
    return devices


def list_local_printers(cidr: str = "192.168.1.0/24") -> List[Dict[str, Any]]:
    return list_cups_printers() + _network_printers(cidr)
