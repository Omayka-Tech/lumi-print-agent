from __future__ import annotations

from lumi_print_gui.install import copy_into_user_dir, needs_self_install


def test_needs_self_install_false_when_not_frozen(monkeypatch):
    monkeypatch.setattr("lumi_print_gui.install.is_frozen", lambda: False)
    assert needs_self_install() is False


def test_needs_self_install_portable_env(monkeypatch):
    monkeypatch.setenv("LUMI_PRINT_PORTABLE", "1")
    monkeypatch.setattr("lumi_print_gui.install.is_frozen", lambda: True)
    assert needs_self_install() is False


def test_copy_into_user_dir_copies_sibling_dlls(monkeypatch, tmp_path):
    src_dir = tmp_path / "download"
    src_dir.mkdir()
    exe = src_dir / "LumiPrintAgent.exe"
    exe.write_bytes(b"fake-exe")
    (src_dir / "python37.dll").write_bytes(b"dll")
    (src_dir / "VCRUNTIME140.dll").write_bytes(b"vcr")
    internal = src_dir / "_internal"
    internal.mkdir()
    (internal / "base_library.zip").write_bytes(b"zip")

    dest = tmp_path / "AppData" / "print-agent"
    dest.mkdir(parents=True)
    (dest / "config.yaml").write_text("printer:\n  host: 1.2.3.4\n", encoding="utf-8")

    monkeypatch.setattr("lumi_print_gui.install.is_frozen", lambda: True)
    monkeypatch.setattr("lumi_print_gui.install.user_data_dir", lambda: dest)
    monkeypatch.setattr("lumi_print_gui.install.sys.executable", str(exe))
    monkeypatch.setattr("lumi_print_gui.install.sys.platform", "win32")

    target = copy_into_user_dir()
    assert target == dest / "LumiPrintAgent.exe"
    assert target.read_bytes() == b"fake-exe"
    assert (dest / "python37.dll").read_bytes() == b"dll"
    assert (dest / "VCRUNTIME140.dll").read_bytes() == b"vcr"
    assert (dest / "_internal" / "base_library.zip").read_bytes() == b"zip"
    # user config preserved
    assert "1.2.3.4" in (dest / "config.yaml").read_text(encoding="utf-8")
