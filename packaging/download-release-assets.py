#!/usr/bin/env python3
"""Download GitHub Release assets for a tag (no gh CLI required)."""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 4:
        print(
            "usage: download-release-assets.py <owner/repo> <tag> <dest_dir>",
            file=sys.stderr,
        )
        return 2

    repo, tag, dest_s = sys.argv[1], sys.argv[2], sys.argv[3]
    token = (
        __import__("os").environ.get("GH_TOKEN")
        or __import__("os").environ.get("GITHUB_TOKEN")
        or ""
    )
    if not token:
        print("error: GH_TOKEN or GITHUB_TOKEN required", file=sys.stderr)
        return 1

    dest = Path(dest_s)
    dest.mkdir(parents=True, exist_ok=True)

    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/releases/tags/{tag}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "lumi-print-agent-mirror",
        },
    )
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)

    assets = data.get("assets") or []
    if not assets:
        print(f"error: release {tag} has no assets", file=sys.stderr)
        return 1

    for asset in assets:
        name = asset["name"]
        url = asset["url"]
        areq = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/octet-stream",
                "User-Agent": "lumi-print-agent-mirror",
            },
        )
        out = dest / name
        with urllib.request.urlopen(areq) as aresp, out.open("wb") as fh:
            fh.write(aresp.read())
        print(f"downloaded {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
