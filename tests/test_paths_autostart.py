from __future__ import annotations

import sys

from lumi_print_agent.paths import user_data_dir
from lumi_print_gui import autostart


def test_user_data_dir_linux(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert user_data_dir() == tmp_path / "lumi" / "print-agent"


def test_linux_autostart_desktop(monkeypatch, tmp_path):
    monkeypatch.setattr(autostart.sys, "platform", "linux")
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(autostart, "is_frozen", lambda: True)
    monkeypatch.setattr(autostart.sys, "executable", str(tmp_path / "LumiPrintAgent"))
    autostart.enable()
    desktop = tmp_path / "autostart" / "lumi-print-agent.desktop"
    assert desktop.is_file()
    text = desktop.read_text(encoding="utf-8")
    assert "LumiPrintAgent" in text
    assert "--hidden" in text
    assert "X-GNOME-Autostart-enabled=true" in text
    assert autostart.is_enabled() is True
    autostart.disable()
    assert desktop.is_file() is False


def test_macos_autostart_plist(monkeypatch, tmp_path):
    plist = tmp_path / "Library" / "LaunchAgents" / "tech.omayka.lumi-print-agent.plist"
    monkeypatch.setattr(autostart.sys, "platform", "darwin")
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(autostart, "macos_plist_path", lambda: plist)
    monkeypatch.setattr(autostart, "is_frozen", lambda: True)
    monkeypatch.setattr(autostart.sys, "executable", str(tmp_path / "LumiPrintAgent"))
    autostart.enable()
    assert plist.is_file()
    text = plist.read_text(encoding="utf-8")
    assert "tech.omayka.lumi-print-agent" in text
    assert "LumiPrintAgent" in text
    assert "--hidden" in text
    autostart.disable()
    assert plist.is_file() is False
