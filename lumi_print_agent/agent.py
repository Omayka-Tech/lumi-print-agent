"""Poll opcional de la cola cloud (apagado por default)."""

from __future__ import annotations

import argparse
import base64
import logging
import os
import signal
import sys
import time
from typing import List, Optional

from .client import PrintAgentClient
from .config import AgentConfig, load_config
from .drivers import send_payload
from .state import RUNTIME

logger = logging.getLogger("lumi_print_agent")
_shutdown = False


def _handle_sigterm(*_args: object) -> None:
    global _shutdown
    _shutdown = True


def process_queue_once(cfg: AgentConfig) -> List[int]:
    if not cfg.has_cloud():
        raise RuntimeError("Poll requiere api_url y api_key/token")
    client = PrintAgentClient(cfg)
    processed: List[int] = []
    for job in client.fetch_queue(limit=cfg.queue_limit):
        job_id = int(job["id"])
        if not client.claim(job_id):
            continue
        try:
            payload = client.fetch_payload(job_id)
            raw = base64.b64decode(payload["content_base64"])
            send_payload(
                payload["driver_id"],
                raw,
                payload.get("connection_detail") or {},
                payload.get("profile") or {},
            )
            client.complete(job_id, success=True)
            processed.append(job_id)
            RUNTIME.record(True, detail="job {}".format(job_id))
            logger.info("Job %s impreso OK", job_id)
        except Exception as exc:
            logger.error("Job %s falló: %s", job_id, exc)
            RUNTIME.record(False, error=str(exc))
            try:
                client.complete(job_id, success=False, error=str(exc))
            except Exception:
                pass
    return processed


def run_loop(config_path: str) -> int:
    global _shutdown
    cfg = load_config(config_path)
    logging.basicConfig(
        level=getattr(logging, cfg.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGINT, _handle_sigterm)
    logger.info("Poll iniciado tenant_host=%s interval=%ss", cfg.tenant_host, cfg.poll_interval)

    backoff = 1.0
    while not _shutdown:
        try:
            processed = process_queue_once(cfg)
            if processed:
                logger.info("Ciclo OK: jobs %s", processed)
            backoff = 1.0
        except Exception as exc:
            logger.error("Error en loop: %s", exc)
            time.sleep(min(backoff, 60))
            backoff = min(backoff * 2, 60)
            continue
        time.sleep(cfg.poll_interval)
    logger.info("Poll detenido")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    from .local_api import serve_headless

    parser = argparse.ArgumentParser(description="Lumi print agent (headless)")
    parser.add_argument("--config", default=os.environ.get("LUMI_PRINT_AGENT_CONFIG") or "", help="Ruta YAML")
    parser.add_argument("--host", default="", help="Bind HTTP (default: config / 127.0.0.1)")
    parser.add_argument("--port", type=int, default=0, help="Puerto HTTP (default: 17890)")
    parser.add_argument("--poll-only", action="store_true", help="Solo cola cloud, sin API local")
    parser.add_argument("--no-poll", action="store_true", help="Solo API local, sin poll")
    args = parser.parse_args(argv)
    config_path = args.config or None
    if args.poll_only:
        return run_loop(config_path or "")
    return serve_headless(
        host=args.host or None,
        port=args.port or None,
        config_path=config_path,
        enable_poll=not args.no_poll,
    )


if __name__ == "__main__":
    sys.exit(main())
