#!/usr/bin/env bash
# Build a curated index.html for the printer-agent downloads tree.
# Usage: packaging/generate-downloads-index.sh /path/to/printer-agent
set -euo pipefail

ROOT_DIR="${1:?downloads root required (…/printer-agent)}"
BASE_URL="${DOWNLOADS_BASE_URL:-https://downloads.lumi.com.py}"

if [[ ! -d "${ROOT_DIR}" ]]; then
  echo "error: ${ROOT_DIR} is not a directory" >&2
  exit 1
fi

python3 - "${ROOT_DIR}" "${BASE_URL}" <<'PY'
import html
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
base = sys.argv[2].rstrip("/")

versions = sorted(
    (p for p in root.iterdir() if p.is_dir() and p.name.startswith("v")),
    key=lambda p: p.name,
    reverse=True,
)

def files_for(dir_path: pathlib.Path):
    skip = {"index.html"}
    return sorted(
        p for p in dir_path.iterdir()
        if p.is_file() and p.name not in skip and not p.name.startswith(".")
    )

latest = root / "latest"
latest_files = files_for(latest) if latest.is_dir() else []

parts = [
    "<!DOCTYPE html>",
    '<html lang="es">',
    "<head>",
    '<meta charset="utf-8">',
    '<meta name="viewport" content="width=device-width, initial-scale=1">',
    "<title>Lumi Print Agent — descargas</title>",
    "<style>",
    "body{font-family:system-ui,sans-serif;max-width:52rem;margin:2rem auto;padding:0 1rem;line-height:1.45;color:#1a1a1a}",
    "h1{font-size:1.5rem} h2{font-size:1.15rem;margin-top:2rem}",
    "ul{padding-left:1.2rem} a{color:#0b57d0} .meta{color:#555;font-size:.9rem}",
    "</style>",
    "</head>",
    "<body>",
    "<h1>Lumi Print Agent</h1>",
    '<p class="meta">Descargas oficiales. Sin listado automático del disco.</p>',
]

if latest_files:
    parts.append("<h2>Última versión (latest)</h2>")
    parts.append("<ul>")
    for f in latest_files:
        href = f"{base}/latest/{html.escape(f.name)}"
        parts.append(f'<li><a href="{href}">{html.escape(f.name)}</a></li>')
    parts.append("</ul>")
else:
    parts.append("<p>Aún no hay archivos en <code>latest/</code>.</p>")

parts.append("<h2>Versiones</h2>")
if not versions:
    parts.append("<p>Sin versiones publicadas todavía.</p>")
else:
    for ver_dir in versions:
        parts.append(f"<h3>{html.escape(ver_dir.name)}</h3>")
        files = files_for(ver_dir)
        if not files:
            parts.append("<p><em>(vacío)</em></p>")
            continue
        parts.append("<ul>")
        for f in files:
            href = f"{base}/{html.escape(ver_dir.name)}/{html.escape(f.name)}"
            parts.append(f'<li><a href="{href}">{html.escape(f.name)}</a></li>')
        parts.append("</ul>")

parts.extend(
    [
        '<p class="meta">También en '
        '<a href="https://github.com/Omayka-Tech/lumi-print-agent/releases">GitHub Releases</a>.'
        "</p>",
        "</body>",
        "</html>",
        "",
    ]
)

index_body = "\n".join(parts)
(root / "index.html").write_text(index_body, encoding="utf-8")
print(f"Wrote {root / 'index.html'}")

# So /latest/ resolves without autoindex.
if latest.is_dir():
    latest_parts = [
        "<!DOCTYPE html>",
        '<html lang="es">',
        "<head>",
        '<meta charset="utf-8">',
        "<title>Lumi Print Agent — latest</title>",
        "</head>",
        "<body>",
        "<h1>Lumi Print Agent — latest</h1>",
        '<p><a href="/">← todas las versiones</a></p>',
        "<ul>",
    ]
    for f in latest_files:
        href = f"{base}/latest/{html.escape(f.name)}"
        latest_parts.append(f'<li><a href="{href}">{html.escape(f.name)}</a></li>')
    latest_parts.extend(["</ul>", "</body>", "</html>", ""])
    (latest / "index.html").write_text("\n".join(latest_parts), encoding="utf-8")
    print(f"Wrote {latest / 'index.html'}")
PY
