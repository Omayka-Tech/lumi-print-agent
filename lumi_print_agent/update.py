"""Actualización desde downloads.lumi.com.py / GitHub Releases."""

from __future__ import annotations

import platform
import re
import shutil
import sys
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from .version import current_version, is_newer

DOWNLOADS_BASE = "https://downloads.lumi.com.py"
GITHUB_REPO = "Omayka-Tech/lumi-print-agent"
USER_AGENT = "lumi-print-agent-updater"

_ASSET_RE = re.compile(
    r"LumiPrintAgent-(?P<os>windows|macos|linux)-(?P<arch>[^-]+)-v"
    r"(?P<ver>\d+\.\d+\.\d+(?:[.-][0-9A-Za-z.-]+)?)\.(?P<ext>zip|tar\.gz)",
    re.I,
)


@dataclass
class ReleaseInfo:
    version: str
    asset_name: str
    url: str
    source: str
    notes: str = ""

    @property
    def update_available(self) -> bool:
        return is_newer(self.version, current_version())


def platform_tokens() -> Tuple[str, str, str]:
    """Return (os_token, arch_token, extension)."""
    machine = platform.machine().lower()
    if machine in ("aarch64", "arm64"):
        arch = "arm64"
    elif machine in ("x86_64", "amd64", "i386", "i686", "x86"):
        arch = "x86_64"
    else:
        arch = machine or "x86_64"
    if sys.platform == "win32":
        return "windows", "x86_64", "zip"
    if sys.platform == "darwin":
        return "macos", arch, "tar.gz"
    return "linux", "x86_64" if arch.startswith("x86") else arch, "tar.gz"


def check_for_update(timeout: float = 12.0) -> Optional[ReleaseInfo]:
    """Consulta GitHub Releases (público); si falla, espejo downloads.lumi.com.py."""
    errors: List[str] = []
    # GitHub primero: el espejo a veces sirve el SPA de Lumi en /latest/.
    for finder in (_from_github, _from_downloads):
        try:
            info = finder(timeout=timeout)
        except Exception as exc:  # noqa: BLE001 — best-effort cascade
            errors.append("{}: {}".format(finder.__name__, exc))
            continue
        if info is not None:
            return info
    if errors:
        raise RuntimeError("; ".join(errors))
    return None


def download_and_extract(info: ReleaseInfo, dest: Optional[Path] = None, timeout: float = 120.0) -> Path:
    """Baja el archivo del release y deja el árbol ``LumiPrintAgent/`` en dest."""
    root = Path(dest) if dest else Path(tempfile.mkdtemp(prefix="lumi-print-update-"))
    root.mkdir(parents=True, exist_ok=True)
    archive = root / info.asset_name
    _download(info.url, archive, timeout=timeout)
    extract_dir = root / "extracted"
    if extract_dir.exists():
        shutil.rmtree(str(extract_dir))
    extract_dir.mkdir(parents=True, exist_ok=True)
    if info.asset_name.lower().endswith(".zip"):
        with zipfile.ZipFile(str(archive), "r") as zf:
            zf.extractall(str(extract_dir))
    else:
        with tarfile.open(str(archive), "r:gz") as tf:
            tf.extractall(str(extract_dir))
    tree = _find_app_tree(extract_dir)
    if tree is None:
        raise RuntimeError("El release no contiene la carpeta LumiPrintAgent")
    return tree


def apply_extracted_update(tree: Path, relaunch: bool = True, hidden: bool = True) -> Path:
    """Copia el árbol liberado sobre la instalación de usuario y relanza."""
    from lumi_print_gui.install import copy_tree_into_user_dir, relaunch_installed

    target = copy_tree_into_user_dir(tree)
    if relaunch:
        args = ["--hidden"] if hidden else []
        relaunch_installed(extra_args=args)
    return target


def _from_downloads(timeout: float = 12.0) -> Optional[ReleaseInfo]:
    os_token, arch_token, ext = platform_tokens()
    sha_url = "{}/latest/SHA256SUMS".format(DOWNLOADS_BASE.rstrip("/"))
    text = _http_text(sha_url, timeout=timeout)
    chosen: Optional[Tuple[str, str]] = None  # version, name
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        name = parts[-1].lstrip("*")
        match = _ASSET_RE.search(name)
        if not match:
            continue
        if match.group("os").lower() != os_token:
            continue
        if match.group("arch").lower() != arch_token:
            continue
        if match.group("ext").lower() != ext:
            continue
        ver = match.group("ver")
        if chosen is None or is_newer(ver, chosen[0]):
            chosen = (ver, name)
    if chosen is None:
        # fallback: parse latest/index.html links
        html = _http_text("{}/latest/".format(DOWNLOADS_BASE.rstrip("/")), timeout=timeout)
        for match in _ASSET_RE.finditer(html):
            if match.group("os").lower() != os_token or match.group("arch").lower() != arch_token:
                continue
            if match.group("ext").lower() != ext:
                continue
            ver = match.group("ver")
            name = match.group(0)
            if chosen is None or is_newer(ver, chosen[0]):
                chosen = (ver, name)
    if chosen is None:
        return None
    ver, name = chosen
    return ReleaseInfo(
        version=ver,
        asset_name=name,
        url="{}/latest/{}".format(DOWNLOADS_BASE.rstrip("/"), name),
        source="downloads.lumi.com.py",
    )


def _from_github(timeout: float = 12.0) -> Optional[ReleaseInfo]:
    os_token, arch_token, ext = platform_tokens()
    api = "https://api.github.com/repos/{}/releases/latest".format(GITHUB_REPO)
    data = _http_json(api, timeout=timeout)
    tag = str(data.get("tag_name") or "").lstrip("v")
    notes = str(data.get("body") or "")
    assets = data.get("assets") or []
    for asset in assets:
        name = str(asset.get("name") or "")
        match = _ASSET_RE.search(name)
        if not match:
            continue
        if match.group("os").lower() != os_token:
            continue
        if match.group("arch").lower() != arch_token:
            continue
        if match.group("ext").lower() != ext:
            continue
        url = str(asset.get("browser_download_url") or "")
        if not url:
            continue
        return ReleaseInfo(
            version=match.group("ver") or tag,
            asset_name=name,
            url=url,
            source="github",
            notes=notes,
        )
    return None


def _find_app_tree(root: Path) -> Optional[Path]:
    direct = root / "LumiPrintAgent"
    if direct.is_dir():
        return direct
    for path in root.rglob("LumiPrintAgent"):
        if path.is_dir():
            return path
    return None


def _ssl_verify():
    """CA bundle embebido (PyInstaller/Win7 no ve bien el store del sistema)."""
    try:
        import certifi

        return certifi.where()
    except Exception:
        return True


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    session.verify = _ssl_verify()
    return session


def _download(url: str, dest: Path, timeout: float = 120.0) -> None:
    with _session().get(url, timeout=timeout, stream=True, allow_redirects=True) as resp:
        resp.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in resp.iter_content(chunk_size=1024 * 256):
                if chunk:
                    fh.write(chunk)


def _http_text(url: str, timeout: float = 12.0) -> str:
    resp = _session().get(
        url,
        timeout=timeout,
        headers={"Accept": "text/plain,text/html,*/*"},
        allow_redirects=True,
    )
    resp.raise_for_status()
    return resp.text


def _http_json(url: str, timeout: float = 12.0) -> Dict[str, Any]:
    resp = _session().get(
        url,
        timeout=timeout,
        headers={"Accept": "application/vnd.github+json"},
        allow_redirects=True,
    )
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise ValueError("JSON object requerido")
    return data
