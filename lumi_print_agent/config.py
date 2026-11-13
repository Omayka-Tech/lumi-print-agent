"""Configuración YAML del agente (impresora local + poll opcional)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from .paths import default_config_path, user_data_dir


@dataclass
class PrinterSettings:
    host: str = ""
    port: int = 9100
    driver_id: str = "escpos_network"
    timeout: float = 10.0
    cidr: str = ""
    manufacturer: str = ""
    model: str = ""
    serial: str = ""

    def label(self) -> str:
        parts = [self.manufacturer, self.model]
        text = " ".join(p for p in parts if p).strip()
        if text and self.model.upper().startswith(self.manufacturer.upper()) and self.manufacturer:
            text = self.model
        return text


@dataclass
class AgentConfig:
    printer: PrinterSettings = field(default_factory=PrinterSettings)
    autostart: bool = False
    local_api_host: str = "127.0.0.1"
    local_api_port: int = 17890
    log_level: str = "INFO"
    poll_enabled: bool = False
    api_url: str = ""
    tenant_host: str = ""
    token: str = ""
    poll_interval: float = 5.0
    queue_limit: int = 10
    branch_filter: str = ""

    def has_cloud(self) -> bool:
        return bool(self.token and self.api_url)

    def connection_detail(self) -> Dict[str, Any]:
        return {
            "host": self.printer.host,
            "port": int(self.printer.port),
            "timeout": float(self.printer.timeout),
        }


def _as_printer(raw: Any) -> PrinterSettings:
    if not isinstance(raw, dict):
        return PrinterSettings()
    return PrinterSettings(
        host=str(raw.get("host") or ""),
        port=int(raw.get("port") or 9100),
        driver_id=str(raw.get("driver_id") or "escpos_network"),
        timeout=float(raw.get("timeout") or 10),
        cidr=str(raw.get("cidr") or ""),
        manufacturer=str(raw.get("manufacturer") or ""),
        model=str(raw.get("model") or ""),
        serial=str(raw.get("serial") or ""),
    )


def load_config(path: Optional[str] = None) -> AgentConfig:
    cfg_path = Path(path) if path else default_config_path()
    if not cfg_path.is_file():
        return AgentConfig()
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return AgentConfig()
    credential = data.get("api_key") or data.get("token") or ""
    printer = _as_printer(data.get("printer"))
    if not printer.host and data.get("printer_host"):
        printer.host = str(data.get("printer_host") or "")
    return AgentConfig(
        printer=printer,
        autostart=bool(data.get("autostart", False)),
        local_api_host=str(data.get("local_api_host") or "127.0.0.1"),
        local_api_port=int(data.get("local_api_port") or 17890),
        log_level=str(data.get("log_level") or "INFO"),
        poll_enabled=bool(data.get("poll_enabled", False)),
        api_url=str(data.get("api_url") or "").rstrip("/"),
        tenant_host=str(data.get("tenant_host") or ""),
        token=str(credential or ""),
        poll_interval=float(data.get("poll_interval") or 5),
        queue_limit=int(data.get("queue_limit") or 10),
        branch_filter=str(data.get("branch_filter") or ""),
    )


def save_config(cfg: AgentConfig, path: Optional[str] = None) -> Path:
    cfg_path = Path(path) if path else default_config_path()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    payload: Dict[str, Any] = {
        "printer": asdict(cfg.printer),
        "autostart": cfg.autostart,
        "local_api_host": cfg.local_api_host,
        "local_api_port": cfg.local_api_port,
        "log_level": cfg.log_level,
        "poll_enabled": cfg.poll_enabled,
    }
    if cfg.api_url:
        payload["api_url"] = cfg.api_url
    if cfg.tenant_host:
        payload["tenant_host"] = cfg.tenant_host
    if cfg.token:
        if str(cfg.token).startswith("lumi_"):
            payload["api_key"] = cfg.token
        else:
            payload["token"] = cfg.token
    if cfg.poll_interval != 5.0:
        payload["poll_interval"] = cfg.poll_interval
    if cfg.queue_limit != 10:
        payload["queue_limit"] = cfg.queue_limit
    if cfg.branch_filter:
        payload["branch_filter"] = cfg.branch_filter
    cfg_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return cfg_path


def ensure_user_dir() -> Path:
    path = user_data_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path
