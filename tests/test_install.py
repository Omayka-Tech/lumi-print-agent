from __future__ import annotations

from lumi_print_gui.install import copy_into_user_dir, needs_self_install


def test_needs_self_install_false_when_not_frozen(monkeypatch):
    monkeypatch.setattr("lumi_print_gui.install.is_frozen", lambda: False)
    assert needs_self_install() is False


def test_needs_self_install_portable_env(monkeypatch):
    monkeypatch.setenv("LUMI_PRINT_PORTABLE", "1")
    monkeypatch.setattr("lumi_print_gui.install.is_frozen", lambda: True)
    assert needs_self_install() is False


def test_copy_into_user_dir(monkeypatch, tmp_path):
    src_dir = tmp_path / "download"
    src_dir.mkdir()
    exe = src_dir / "LumiPrintAgent"
    exe.write_bytes(b"fake-exe")
    dest = tmp_path / "AppData" / "print-agent"
    monkeypatch.setattr("lumi_print_gui.install.is_frozen", lambda: True)
    monkeypatch.setattr("lumi_print_gui.install.user_data_dir", lambda: dest)
    monkeypatch.setattr("lumi_print_gui.install.sys.executable", str(exe))
    monkeypatch.setattr("lumi_print_gui.install.sys.platform", "linux")
    target = copy_into_user_dir()
    assert target == dest / "LumiPrintAgent"
    assert target.is_file()
    assert target.read_bytes() == b"fake-exe"
