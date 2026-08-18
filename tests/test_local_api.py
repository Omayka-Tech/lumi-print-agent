"""Tests HTTP de la API local del agente."""

from __future__ import annotations

import base64
import json
import threading
import urllib.error
import urllib.request
from unittest.mock import patch

import pytest

from lumi_print_agent.local_api import LocalApiHandler, ThreadedHTTPServer


@pytest.fixture
def local_server():
    server = ThreadedHTTPServer(("127.0.0.1", 0), LocalApiHandler)
    LocalApiHandler.bind_host = "127.0.0.1"
    LocalApiHandler.bind_port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:{}".format(server.server_address[1])
    server.shutdown()


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode())


def _post(url: str, body: dict):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data, method="POST", headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def test_health(local_server):
    data = _get("{}/health".format(local_server))
    assert data["status"] == "ok"


def test_get_printers(local_server):
    fake = [
        {
            "id": "cups-A",
            "name": "A",
            "driver": "cups_spooler",
            "connection_mode": "os_spooler",
            "connection_detail": {"queue": "A"},
            "is_default": True,
            "source": "cups",
        }
    ]
    with patch("lumi_print_agent.local_api.list_local_printers", return_value=fake):
        data = _get("{}/printers".format(local_server))
    assert data["agent_available"] is True
    assert data["printers"][0]["name"] == "A"


def test_print_direct_ok(local_server):
    payload = base64.b64encode(b"test").decode()
    with patch("lumi_print_agent.local_api.send_payload") as send:
        status, data = _post(
            "{}/print-direct".format(local_server),
            {
                "driver_id": "escpos_network",
                "connection_detail": {"host": "127.0.0.1", "port": 9100},
                "content_base64": payload,
            },
        )
    assert status == 200
    assert data["ok"] is True
    send.assert_called_once()


def test_print_direct_missing_driver(local_server):
    status, data = _post(
        "{}/print-direct".format(local_server),
        {"connection_detail": {}, "content_base64": base64.b64encode(b"x").decode()},
    )
    assert status == 400
    assert "driver_id" in data["detail"]


def test_options_cors(local_server):
    req = urllib.request.Request("{}/health".format(local_server), method="OPTIONS")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 204


def test_status_endpoint(local_server):
    data = _get("{}/status".format(local_server))
    assert data["listening"] is True
    assert "last_job" in data
    assert "printer" in data
