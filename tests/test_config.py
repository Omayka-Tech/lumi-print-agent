"""Config YAML: modo simple no exige API key."""

from __future__ import annotations

from lumi_print_agent.config import load_config, save_config


def test_load_missing_file_returns_defaults(tmp_path):
    cfg = load_config(str(tmp_path / "missing.yaml"))
    assert cfg.printer.port == 9100
    assert cfg.poll_enabled is False
    assert cfg.has_cloud() is False
    assert cfg.local_api_port == 17890


def test_roundtrip_printer_only(tmp_path):
    path = tmp_path / "config.yaml"
    cfg = load_config(str(path))
    cfg.printer.host = "192.168.2.2"
    cfg.printer.port = 9100
    cfg.autostart = True
    save_config(cfg, str(path))
    loaded = load_config(str(path))
    assert loaded.printer.host == "192.168.2.2"
    assert loaded.autostart is True
    assert "api_key" not in path.read_text(encoding="utf-8")


def test_legacy_cloud_yaml(tmp_path):
    path = tmp_path / "legacy.yaml"
    path.write_text(
        "api_url: http://localhost:8000/api/v1\n"
        "tenant_host: tenant1.localhost\n"
        "api_key: lumi_abc\n"
        "poll_interval: 7\n",
        encoding="utf-8",
    )
    cfg = load_config(str(path))
    assert cfg.token == "lumi_abc"
    assert cfg.api_url.endswith("/api/v1")
    assert cfg.has_cloud() is True
    assert cfg.poll_interval == 7
