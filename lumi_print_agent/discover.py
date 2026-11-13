"""Escaneo de ticketeras en subnet (puerto 9100) con identidad ESC/POS."""

from __future__ import annotations

import concurrent.futures
import ipaddress
import socket
from typing import Any, Dict, List, Optional

from .identify import format_identity, identify_escpos


def guess_cidr() -> str:
    """Estima la LAN local /24 a partir de la IP de salida."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
    except OSError:
        return "192.168.1.0/24"
    finally:
        sock.close()
    parts = ip.split(".")
    if len(parts) != 4:
        return "192.168.1.0/24"
    return "{}.{}.{}.0/24".format(parts[0], parts[1], parts[2])


def scan_subnet(
    cidr: Optional[str] = None,
    port: int = 9100,
    timeout: float = 0.3,
    workers: int = 64,
    identify: bool = True,
    identify_timeout: float = 0.8,
) -> List[Dict[str, Any]]:
    net = ipaddress.ip_network(cidr or guess_cidr(), strict=False)
    hosts = [str(h) for h in net.hosts()]

    def probe(host: str) -> Optional[Dict[str, Any]]:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return {
                    "host": host,
                    "port": port,
                    "connection_mode": "network",
                    "printer_type": "thermal",
                    "driver": "escpos_network",
                    "manufacturer": "",
                    "model": "",
                    "serial": "",
                    "firmware": "",
                    "mac": "",
                    "label": "",
                }
        except OSError:
            return None

    found: List[Dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for result in pool.map(probe, hosts):
            if result:
                found.append(result)

    if identify and found:
        def enrich(item: Dict[str, Any]) -> Dict[str, Any]:
            ident = identify_escpos(item["host"], int(item["port"]), timeout=identify_timeout)
            item.update(ident)
            item["label"] = format_identity(ident)
            return item

        id_workers = min(8, len(found))
        with concurrent.futures.ThreadPoolExecutor(max_workers=id_workers) as pool:
            found = list(pool.map(enrich, found))
    return found
