"""Identidad pública de ticketeras ESC/POS (GS I) y OUI IEEE."""

from __future__ import annotations

import re
import socket
import subprocess
import sys
from typing import Any, Dict, Tuple

# Prefijos IEEE públicos de fabricantes POS/térmicos (3 octetos).
# Fuente: IEEE OUI; el nombre comercial sale de GS I cuando la impresora responde.
_OUI_BRANDS = {
    "000048": "EPSON",
    "0026ab": "EPSON",
    "38b800": "EPSON",
    "44d244": "EPSON",
    "64eb8c": "EPSON",
    "9caed3": "EPSON",
    "a4ee57": "EPSON",
    "ac1826": "EPSON",
    "dccd2f": "EPSON",
    "001162": "Star Micronics",
    "001599": "Star Micronics",
    "001b17": "Star Micronics",
    "001d4f": "Star Micronics",
    "002258": "Star Micronics",
    "002308": "Star Micronics",
    "30055c": "Star Micronics",
    "7825ad": "Star Micronics",
    "0015e5": "Bixolon",
    "001f47": "Bixolon",
    "000d4a": "Citizen",
    "00074d": "Zebra",
    "001570": "Zebra",
    "002368": "Zebra",
    "00a0f8": "Zebra",
    "001ba9": "Brother",
    "008077": "Brother",
    "6cc147": "HPRT",
}

_KNOWN_BRANDS = {
    "EPSON",
    "STAR",
    "STAR MICRONICS",
    "BIXOLON",
    "CITIZEN",
    "ZEBRA",
    "BROTHER",
    "HPRT",
    "FTX",
    "XPRINTER",
    "SEIKO",
    "BEMATECH",
    "ELGIN",
    "DARUMA",
    "HP",
    "SAMSUNG",
}

_MAC_RE = re.compile(r"(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}")
_GS_I_MFR = 66  # manufacturer string
_GS_I_NAME = 67  # printer name / model
_GS_I_SERIAL = 68
_GS_I_FW = 65

GS_I_HEADER = 0x5F  # '_'


def empty_identity() -> Dict[str, Any]:
    return {
        "manufacturer": "",
        "model": "",
        "serial": "",
        "firmware": "",
        "mac": "",
        "label": "",
    }


def format_identity(ident: Optional[Dict[str, Any]]) -> str:
    ident = ident or {}
    manufacturer = str(ident.get("manufacturer") or "").strip()
    model = str(ident.get("model") or "").strip()
    if manufacturer and model:
        if model.upper().startswith(manufacturer.upper()):
            return model
        return "{} {}".format(manufacturer, model)
    return model or manufacturer


def printer_label(ident: Optional[Dict[str, Any]], host: str, port: int = 9100) -> str:
    name = format_identity(ident)
    endpoint = "{}:{}".format(host, int(port or 9100))
    if name:
        return "{}  —  {}".format(name, endpoint)
    return endpoint


def parse_gs_i_string(raw: bytes) -> str:
    """Interpreta la respuesta GS I n=65..69: header 0x5F + texto + NUL."""
    if not raw:
        return ""
    data = raw
    if data[:1] == bytes([GS_I_HEADER]):
        data = data[1:]
    nul = data.find(b"\x00")
    if nul >= 0:
        data = data[:nul]
    text = data.decode("utf-8", "replace").strip()
    return " ".join(text.split())


def brand_from_mac(mac: str) -> str:
    prefix = _oui_prefix(mac)
    if not prefix:
        return ""
    return _OUI_BRANDS.get(prefix, "")


def lookup_mac(host: str) -> str:
    """MAC del ARP local (pública en la LAN). Vacío si no hay entrada."""
    if not host:
        return ""
    try:
        if sys.platform == "win32":
            cmd = ["arp", "-a", host]
        else:
            cmd = ["arp", "-n", host]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=2, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    text = (result.stdout or "") + "\n" + (result.stderr or "")
    match = _MAC_RE.search(text)
    if not match:
        return ""
    return _normalize_mac(match.group(0))


def split_cups_description(description: str) -> Tuple[str, str]:
    """Parte 'EPSON TM-T88VII' en marca / modelo usando marcas conocidas."""
    text = " ".join((description or "").replace("_", " ").split())
    if not text:
        return "", ""
    upper = text.upper()
    for brand in sorted(_KNOWN_BRANDS, key=len, reverse=True):
        if upper == brand or upper.startswith(brand + " "):
            rest = text[len(brand) :].strip()
            pretty = _pretty_brand(brand)
            if brand == "STAR" and rest.upper().startswith("MICRONICS"):
                pretty = "Star Micronics"
                rest = rest[len("MICRONICS") :].strip()
            return pretty, rest
    return "", text


def _pretty_brand(brand: str) -> str:
    special = {
        "EPSON": "EPSON",
        "HP": "HP",
        "HPRT": "HPRT",
        "FTX": "FTX",
        "STAR": "Star Micronics",
        "STAR MICRONICS": "Star Micronics",
    }
    return special.get(brand, brand.title())


_GS_I_FIELDS = (
    ("manufacturer", _GS_I_MFR),
    ("model", _GS_I_NAME),
    ("serial", _GS_I_SERIAL),
    ("firmware", _GS_I_FW),
)


def identify_escpos(
    host: str,
    port: int = 9100,
    timeout: float = 0.8,
) -> Dict[str, Any]:
    """Consulta GS I (marca, modelo, serie) y completa con OUI si hace falta."""
    ident = empty_identity()
    ident["mac"] = lookup_mac(host)
    if not host:
        return ident
    ident.update(_read_gs_i_fields(host, port, timeout))
    if not ident["manufacturer"]:
        ident["manufacturer"] = brand_from_mac(ident["mac"])
    ident["label"] = format_identity(ident)
    return ident


def _read_gs_i_fields(host: str, port: int, timeout: float) -> Dict[str, str]:
    """Una sola sesión TCP: las TM-T88 cierran :9100 si se abren cuatro sockets seguidos."""
    out = {"manufacturer": "", "model": "", "serial": "", "firmware": ""}
    sock = None
    try:
        sock = socket.create_connection((host, int(port)), timeout=timeout)
        sock.settimeout(timeout)
        for key, n in _GS_I_FIELDS:
            out[key] = parse_gs_i_string(_query_on_sock(sock, n, timeout))
    except OSError:
        pass
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
    for key, n in _GS_I_FIELDS:
        if out[key]:
            continue
        out[key] = parse_gs_i_string(_query_gs_i(host, port, n, timeout))
    return out


def _query_on_sock(sock: socket.socket, n: int, timeout: float) -> bytes:
    sock.settimeout(timeout)
    sock.sendall(b"\x1dI" + bytes([n]))
    return _recv_until_nul(sock, timeout)


def _query_gs_i(host: str, port: int, n: int, timeout: float) -> bytes:
    try:
        sock = socket.create_connection((host, int(port)), timeout=timeout)
    except OSError:
        return b""
    try:
        return _query_on_sock(sock, n, timeout)
    except OSError:
        return b""
    finally:
        try:
            sock.close()
        except OSError:
            pass


def _recv_until_nul(sock: socket.socket, timeout: float) -> bytes:
    sock.settimeout(timeout)
    data = b""
    try:
        while len(data) < 80:
            chunk = sock.recv(64)
            if not chunk:
                break
            data += chunk
            if b"\x00" in data:
                break
    except socket.timeout:
        pass
    return data


def _normalize_mac(mac: str) -> str:
    hexes = re.findall(r"[0-9A-Fa-f]{2}", mac)
    if len(hexes) != 6:
        return ""
    return ":".join(h.lower() for h in hexes)


def _oui_prefix(mac: str) -> str:
    norm = _normalize_mac(mac)
    if not norm:
        return ""
    return norm.replace(":", "")[:6]
