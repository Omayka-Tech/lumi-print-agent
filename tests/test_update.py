from __future__ import annotations

from lumi_print_agent.update import ReleaseInfo, _ASSET_RE, platform_tokens
from lumi_print_agent.version import current_version, is_newer, parse_version


def test_parse_and_compare_versions():
    assert parse_version("v0.1.2") == (0, 1, 2)
    assert is_newer("0.1.3", "0.1.2") is True
    assert is_newer("0.1.2", "0.1.2") is False
    assert is_newer("0.1.1", "0.1.2") is False


def test_asset_regex_parses_release_name():
    match = _ASSET_RE.search("LumiPrintAgent-macos-arm64-v0.1.2.tar.gz")
    assert match is not None
    assert match.group("os") == "macos"
    assert match.group("arch") == "arm64"
    assert match.group("ver") == "0.1.2"
    assert match.group("ext") == "tar.gz"


def test_platform_tokens_shape():
    os_token, arch, ext = platform_tokens()
    assert os_token in ("windows", "macos", "linux")
    assert arch
    assert ext in ("zip", "tar.gz")


def test_release_info_update_available(monkeypatch):
    monkeypatch.setattr("lumi_print_agent.update.current_version", lambda: "0.1.0")
    info = ReleaseInfo(
        version="0.1.2",
        asset_name="LumiPrintAgent-macos-arm64-v0.1.2.tar.gz",
        url="https://example/x.tar.gz",
        source="test",
    )
    assert info.update_available is True


def test_from_downloads_parses_sha256sums(monkeypatch):
    from lumi_print_agent import update

    monkeypatch.setattr(update, "platform_tokens", lambda: ("macos", "arm64", "tar.gz"))
    monkeypatch.setattr(
        update,
        "_http_text",
        lambda url, timeout=12.0: (
            "abc  LumiPrintAgent-macos-arm64-v0.1.2.tar.gz\n"
            "def  LumiPrintAgent-windows-x86_64-v0.1.2.zip\n"
        ),
    )
    info = update._from_downloads()
    assert info is not None
    assert info.version == "0.1.2"
    assert info.asset_name.endswith("macos-arm64-v0.1.2.tar.gz")
    assert "downloads.lumi.com.py/latest/" in info.url


def test_current_version_nonzero():
    assert current_version()


def test_ssl_verify_uses_certifi(monkeypatch):
    from lumi_print_agent import update

    monkeypatch.setattr(
        "certifi.where",
        lambda: "/tmp/fake-cacert.pem",
        raising=False,
    )
    # Import path used inside _ssl_verify
    import certifi

    monkeypatch.setattr(certifi, "where", lambda: "/tmp/fake-cacert.pem")
    assert update._ssl_verify() == "/tmp/fake-cacert.pem"


def test_check_for_update_prefers_github(monkeypatch):
    from lumi_print_agent import update

    calls = []

    def fake_github(timeout=12.0):
        calls.append("github")
        return update.ReleaseInfo(
            version="0.1.5",
            asset_name="LumiPrintAgent-macos-arm64-v0.1.5.tar.gz",
            url="https://example/x.tar.gz",
            source="github",
        )

    def fake_downloads(timeout=12.0):
        calls.append("downloads")
        raise AssertionError("downloads no debería llamarse si GitHub responde")

    monkeypatch.setattr(update, "_from_github", fake_github)
    monkeypatch.setattr(update, "_from_downloads", fake_downloads)
    info = update.check_for_update()
    assert info is not None
    assert info.source == "github"
    assert calls == ["github"]
