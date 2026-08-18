"""Drivers locales (red :9100, USB raw, CUPS)."""

from __future__ import annotations

import socket
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict

from .test_ticket import build_test_ticket


def send_payload(
    driver_id: str,
    payload_bytes: bytes,
    connection_detail: Dict[str, Any],
    profile: Dict[str, Any],
) -> None:
    if driver_id in ("escpos_network", "raw_network"):
        _escpos_network(payload_bytes, connection_detail)
    elif driver_id == "escpos_usb":
        path = connection_detail.get("device_path")
        if not path:
            raise ValueError("device_path requerido")
        with open(path, "wb") as dev:
            dev.write(payload_bytes)
    elif driver_id in ("cups_spooler", "pdf_spooler"):
        queue = connection_detail.get("queue")
        if not queue:
            raise ValueError("queue CUPS requerido")
        is_html = payload_bytes.lstrip().startswith(b"<") or b"<html" in payload_bytes[:256].lower()
        suffix = ".html" if is_html else (".pdf" if payload_bytes[:4] == b"%PDF" else ".bin")
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(payload_bytes)
            path = tmp.name
        try:
            lp_cmd = ["lp", "-d", queue, path]
            if is_html:
                lp_cmd = ["lp", "-d", queue, "-o", "document-format=text/html", path]
            subprocess.run(lp_cmd, check=True, capture_output=True, timeout=60)
        except subprocess.CalledProcessError as exc:
            err = (exc.stderr or b"").decode() if isinstance(exc.stderr, (bytes, bytearray)) else (exc.stderr or "")
            raise RuntimeError(err.strip() or "lp exit {}".format(exc.returncode)) from exc
        finally:
            Path(path).unlink()
    else:
        raise ValueError("Driver no soportado: {}".format(driver_id))


def send_test_print(connection_detail: Dict[str, Any], driver_id: str = "escpos_network") -> None:
    send_payload(driver_id, build_test_ticket(), connection_detail, {})


def _escpos_network(payload_bytes: bytes, connection_detail: Dict[str, Any]) -> None:
    host = connection_detail.get("host")
    if not host:
        raise ValueError("host requerido para impresora de red")
    port = int(connection_detail.get("port") or 9100)
    timeout = float(connection_detail.get("timeout") or 10)
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall(payload_bytes)
