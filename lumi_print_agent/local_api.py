"""API local en 127.0.0.1:17890 — tubo Chrome → agente → impresora."""

from __future__ import annotations

import base64
import json
import logging
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from .config import load_config
from .discover import guess_cidr, scan_subnet
from .drivers import send_payload
from .os_printers import list_local_printers
from .paths import default_config_path
from .state import RUNTIME

logger = logging.getLogger("lumi_print_agent.local_api")

MAX_PRINT_DIRECT_BYTES = 5 * 1024 * 1024
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 17890


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _allowed_origin(origin: Optional[str]) -> str:
    if not origin:
        return "http://localhost:3000"
    if "localhost" in origin or "127.0.0.1" in origin:
        return origin
    return "http://localhost:3000"


def _validate_print_direct(body: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bytes, Dict[str, Any]]:
    driver_id = body.get("driver_id")
    if not isinstance(driver_id, str) or not driver_id.strip():
        raise ValueError("driver_id requerido")
    connection_detail = body.get("connection_detail")
    if not isinstance(connection_detail, dict):
        raise ValueError("connection_detail requerido")
    content_b64 = body.get("content_base64")
    if not isinstance(content_b64, str) or not content_b64:
        raise ValueError("content_base64 requerido")
    try:
        raw = base64.b64decode(content_b64, validate=True)
    except Exception as exc:
        raise ValueError("content_base64 inválido") from exc
    if len(raw) > MAX_PRINT_DIRECT_BYTES:
        raise ValueError("payload excede {} bytes".format(MAX_PRINT_DIRECT_BYTES))
    profile = body.get("profile") if isinstance(body.get("profile"), dict) else {}
    driver = driver_id.strip()
    if driver in ("escpos_network", "raw_network") and not connection_detail.get("host"):
        raise ValueError("host requerido para impresora de red")
    if driver == "escpos_usb" and not connection_detail.get("device_path"):
        raise ValueError("device_path requerido para USB")
    if driver in ("cups_spooler", "pdf_spooler") and not connection_detail.get("queue"):
        raise ValueError("queue requerido para CUPS")
    return driver, connection_detail, raw, profile


class LocalApiHandler(BaseHTTPRequestHandler):
    config_path: str = os.environ.get("LUMI_PRINT_AGENT_CONFIG") or str(default_config_path())
    bind_host: str = DEFAULT_HOST
    bind_port: int = DEFAULT_PORT

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _cors(self) -> None:
        origin = _allowed_origin(self.headers.get("Origin"))
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_PRINT_DIRECT_BYTES + 65536:
            raise ValueError("body demasiado grande")
        raw = self.rfile.read(length) if length else b"{}"
        data = json.loads(raw.decode("utf-8") or "{}")
        if not isinstance(data, dict):
            raise ValueError("JSON object requerido")
        return data

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._json(200, {"status": "ok", "port": self.bind_port})
            return
        if parsed.path == "/status":
            cfg = load_config(self.config_path)
            self._json(
                200,
                {
                    "listening": True,
                    "host": self.bind_host,
                    "port": self.bind_port,
                    "printer": {
                        "host": cfg.printer.host,
                        "port": cfg.printer.port,
                        "driver_id": cfg.printer.driver_id,
                    },
                    "last_job": RUNTIME.snapshot(),
                },
            )
            return
        if parsed.path == "/discover":
            qs = parse_qs(parsed.query)
            cidr = (qs.get("cidr") or [guess_cidr()])[0]
            devices = scan_subnet(cidr)
            self._json(200, {"devices": devices, "cidr": cidr})
            return
        if parsed.path == "/printers":
            qs = parse_qs(parsed.query)
            cidr = (qs.get("cidr") or [guess_cidr()])[0]
            printers = list_local_printers(cidr)
            self._json(200, {"printers": printers, "agent_available": True, "cidr": cidr})
            return
        self._json(404, {"detail": "not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/print-direct":
            try:
                body = self._read_json_body()
                driver_id, connection_detail, raw, profile = _validate_print_direct(body)
                send_payload(driver_id, raw, connection_detail, profile)
                RUNTIME.record(True, detail="print-direct {} bytes".format(len(raw)))
                self._json(200, {"ok": True})
            except ValueError as exc:
                RUNTIME.record(False, error=str(exc))
                self._json(400, {"detail": str(exc)})
            except Exception as exc:
                RUNTIME.record(False, error=str(exc))
                self._json(500, {"detail": str(exc)})
            return
        if parsed.path == "/ui/open":
            cb = RUNTIME.open_ui
            if cb is None:
                self._json(404, {"detail": "GUI no activa"})
                return
            try:
                cb()
            except Exception as exc:
                self._json(500, {"detail": str(exc)})
                return
            self._json(200, {"ok": True})
            return
        if parsed.path == "/process-once":
            try:
                from .agent import process_queue_once

                cfg = load_config(self.config_path)
                results = process_queue_once(cfg)
                self._json(
                    200,
                    {
                        "processed": len(results),
                        "printed": len(results),
                        "job_ids": results,
                    },
                )
            except FileNotFoundError:
                self._json(
                    503,
                    {"detail": "Config del agente no encontrada. Configure LUMI_PRINT_AGENT_CONFIG."},
                )
            except Exception as exc:
                self._json(500, {"detail": str(exc)})
            return
        self._json(404, {"detail": "not found"})


def make_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    config_path: Optional[str] = None,
) -> ThreadedHTTPServer:
    if config_path:
        LocalApiHandler.config_path = config_path
    LocalApiHandler.bind_host = host
    LocalApiHandler.bind_port = port
    return ThreadedHTTPServer((host, port), LocalApiHandler)


def serve(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, config_path: Optional[str] = None) -> None:
    server = make_server(host=host, port=port, config_path=config_path)
    server.serve_forever()


def probe_running(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            req = (
                "GET /health HTTP/1.1\r\nHost: {}:{}\r\nConnection: close\r\n\r\n".format(host, port)
            ).encode("ascii")
            sock.sendall(req)
            data = sock.recv(1024)
            return b'"status"' in data and b"ok" in data
    except OSError:
        return False


def ask_existing_to_open(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1) as sock:
            body = b"{}"
            req = (
                "POST /ui/open HTTP/1.1\r\n"
                "Host: {}:{}\r\n"
                "Content-Type: application/json\r\n"
                "Content-Length: {}\r\n"
                "Connection: close\r\n\r\n"
            ).format(host, port, len(body)).encode("ascii") + body
            sock.sendall(req)
            data = sock.recv(1024)
            return b'"ok"' in data
    except OSError:
        return False


def serve_headless(
    host: Optional[str] = None,
    port: Optional[int] = None,
    config_path: Optional[str] = None,
    enable_poll: bool = True,
) -> int:
    cfg = load_config(config_path)
    bind_host = host or cfg.local_api_host or DEFAULT_HOST
    bind_port = int(port or cfg.local_api_port or DEFAULT_PORT)
    cfg_path = config_path or str(default_config_path())
    if probe_running(bind_host if bind_host != "0.0.0.0" else DEFAULT_HOST, bind_port):
        logger.info("Puerto %s ocupado: el agente ya está en ejecución", bind_port)
        print("El agente ya está en ejecución (puerto {}).".format(bind_port))
        return 0
    try:
        server = make_server(host=bind_host, port=bind_port, config_path=cfg_path)
    except OSError:
        print("El agente ya está en ejecución (puerto {}).".format(bind_port))
        return 0

    poll_thread = None
    if enable_poll and cfg.poll_enabled and cfg.has_cloud():
        from .agent import run_loop

        poll_thread = threading.Thread(target=run_loop, args=(cfg_path,), daemon=True)
        poll_thread.start()
        logger.info("Poll cloud habilitado")

    env_headless = os.environ.get("LUMI_PRINT_HEADLESS", "")
    logger.info(
        "API local http://%s:%s (headless=%s)",
        bind_host,
        bind_port,
        env_headless or "1",
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
    return 0
