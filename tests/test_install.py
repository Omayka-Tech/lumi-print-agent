from __future__ import annotations

import os
import shutil

from lumi_print_gui.install import copy_into_user_dir, needs_self_install, self_install_and_relaunch


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


def test_copy_replaces_locked_dll(monkeypatch, tmp_path):
    src_dir = tmp_path / "download"
    src_dir.mkdir()
    exe = src_dir / "LumiPrintAgent.exe"
    exe.write_bytes(b"fake-exe")
    (src_dir / "libcrypto-1_1.dll").write_bytes(b"new-crypto")

    dest = tmp_path / "AppData" / "print-agent"
    dest.mkdir(parents=True)
    locked = dest / "libcrypto-1_1.dll"
    locked.write_bytes(b"old-crypto")

    real_copy2 = shutil.copy2

    def flaky_copy2(src, dst, *args, **kwargs):
        if os.path.basename(str(src)) == "libcrypto-1_1.dll" and os.path.exists(dst):
            if not getattr(flaky_copy2, "raised", False):
                flaky_copy2.raised = True
                raise PermissionError(13, "Permission denied", dst)
        return real_copy2(src, dst, *args, **kwargs)

    monkeypatch.setattr("lumi_print_gui.install.shutil.copy2", flaky_copy2)
    monkeypatch.setattr("lumi_print_gui.install.user_data_dir", lambda: dest)
    monkeypatch.setattr("lumi_print_gui.install.sys.executable", str(exe))
    monkeypatch.setattr("lumi_print_gui.install.sys.platform", "win32")

    target = copy_into_user_dir()
    assert target == dest / "LumiPrintAgent.exe"
    assert locked.read_bytes() == b"new-crypto"
    assert (dest / "libcrypto-1_1.dll.stale").read_bytes() == b"old-crypto"


def test_self_install_focuses_agent_that_will_not_exit(monkeypatch, tmp_path):
    dest = tmp_path / "print-agent"
    dest.mkdir()
    calls = []

    monkeypatch.setattr("lumi_print_gui.install._stop_other_instances", lambda: calls.append("stop"))
    monkeypatch.setattr(
        "lumi_print_gui.install.copy_into_user_dir",
        lambda: calls.append("copy") or dest,
    )
    monkeypatch.setattr("lumi_print_gui.install.relaunch_installed", lambda extra_args=None: calls.append("relaunch"))

    def _probe():
        calls.append("probe")
        return True

    def _open():
        calls.append("open")
        return True

    monkeypatch.setattr("lumi_print_agent.local_api.probe_running", _probe)
    monkeypatch.setattr("lumi_print_agent.local_api.ask_existing_to_open", _open)

    assert self_install_and_relaunch() == 0
    assert calls == ["probe", "stop", "probe", "open"]
