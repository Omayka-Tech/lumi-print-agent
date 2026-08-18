"""Cliente HTTP hacia la cola worker de impresión en Lumi (modo avanzado)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import requests

from .config import AgentConfig

logger = logging.getLogger(__name__)


class PrintAgentClient:
    def __init__(self, cfg: AgentConfig) -> None:
        self.cfg = cfg
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": "Bearer {}".format(cfg.token),
                "Host": cfg.tenant_host,
                "Content-Type": "application/json",
            }
        )

    def _url(self, path: str) -> str:
        return "{}/printing/jobs/{}".format(self.cfg.api_url, path)

    def fetch_queue(self, limit: int = 10) -> List[Dict[str, Any]]:
        r = self.session.get(self._url("worker-queue/"), params={"limit": limit}, timeout=30)
        r.raise_for_status()
        return r.json()

    def claim(self, job_id: int) -> bool:
        r = self.session.post(self._url("{}/claim/".format(job_id)), json={}, timeout=30)
        if r.status_code == 409:
            return False
        r.raise_for_status()
        return True

    def fetch_payload(self, job_id: int) -> Dict[str, Any]:
        r = self.session.get(self._url("{}/payload/".format(job_id)), timeout=60)
        r.raise_for_status()
        return r.json()

    def complete(self, job_id: int, success: bool, error: str = "") -> None:
        r = self.session.post(
            self._url("{}/complete/".format(job_id)),
            json={"success": success, "error": error},
            timeout=30,
        )
        r.raise_for_status()
