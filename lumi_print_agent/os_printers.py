"""Listado de impresoras del sistema (CUPS) y red local."""

from __future__ import annotations

import re
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from .discover import scan_subnet
from .identify import printer_label, split_cups_description

_LPSTAT_PRINTER_RE = re.compile(r"^printer\s+(\S+)")
_LPSTAT_DESC_RE = re.compile(r"^\s*Description:\s*(.*)$")
_LPSTAT_DEVICE_RE = re.compile(r"^device for\s+(\S+):\s+(\S+)")
_SOCKET_URI_RE = re.compile(r"^socket://([^:/]+)(?::(\d+))?", re.I)


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


def _cups_descriptions() -> Dict[str, str]:
    out = _run_lpstat("-l", "-p")
    if not out:
        return {}
    current = ""
    found: Dict[str, str] = {}
    for line in out.splitlines():
        match = _LPSTAT_PRINTER_RE.match(line.strip())
        if match:
            current = match.group(1)
            continue
        desc = _LPSTAT_DESC_RE.match(line)
        if desc and current:
            found[current] = desc.group(1).strip()
    return found


def _cups_devices() -> Dict[str, str]:
    out = _run_lpstat("-v")
    if not out:
        return {}
    found: Dict[str, str] = {}
    for line in out.splitlines():
        match = _LPSTAT_DEVICE_RE.match(line.strip())
        if match:
            found[match.group(1)] = match.group(2)
    return found


def _host_port_from_uri(uri: str) -> Tuple[str, Optional[int]]:
    match = _SOCKET_URI_RE.match(uri or "")
    if not match:
        return "", None
    host = match.group(1)
    port = int(match.group(2)) if match.group(2) else 9100
    return host, port


def list_cups_printers(network_by_host: Optional[Dict[str, Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    out = _run_lpstat("-p")
    if out is None:
        return []
    default_queue = _default_cups_queue()
    descriptions = _cups_descriptions()
    devices = _cups_devices()
    network_by_host = network_by_host or {}
    printers: List[Dict[str, Any]] = []
    for line in out.splitlines():
        match = _LPSTAT_PRINTER_RE.match(line.strip())
        if not match:
            continue
        queue = match.group(1)
        description = descriptions.get(queue) or queue.replace("_", " ")
        manufacturer, model = split_cups_description(description)
        uri = devices.get(queue) or ""
        host, port = _host_port_from_uri(uri)
        net = network_by_host.get(host) if host else None
        if net:
            manufacturer = manufacturer or str(net.get("manufacturer") or "")
            model = model or str(net.get("model") or "")
        ident = {"manufacturer": manufacturer, "model": model}
        friendly = printer_label(ident, host, port or 9100) if host else (
            " ".join(part for part in (manufacturer, model) if part).strip() or description
        )
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
                "manufacturer": manufacturer,
                "model": model,
                "label": friendly,
            }
        )
    return printers


def _network_printers(cidr: str) -> List[Dict[str, Any]]:
    devices: List[Dict[str, Any]] = []
    for item in scan_subnet(cidr):
        host = item["host"]
        port = int(item.get("port") or 9100)
        ident = {
            "manufacturer": item.get("manufacturer") or "",
            "model": item.get("model") or "",
        }
        label = item.get("label") or printer_label(ident, host, port)
        devices.append(
            {
                "id": "net-{}-{}".format(host, port),
                "name": label,
                "driver": item.get("driver") or "escpos_network",
                "connection_mode": "network",
                "connection_detail": {"host": host, "port": port},
                "is_default": False,
                "source": "network",
                "printer_type": item.get("printer_type") or "thermal",
                "manufacturer": ident["manufacturer"],
                "model": ident["model"],
                "serial": item.get("serial") or "",
                "firmware": item.get("firmware") or "",
                "mac": item.get("mac") or "",
                "label": label,
            }
        )
    return devices


def list_local_printers(cidr: str = "192.168.1.0/24") -> List[Dict[str, Any]]:
    network = _network_printers(cidr)
    by_host = {}
    for item in network:
        host = (item.get("connection_detail") or {}).get("host")
        if host:
            by_host[host] = item
    return list_cups_printers(by_host) + network
