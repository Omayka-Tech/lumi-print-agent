#!/usr/bin/env bash
# Align VERSION + pyproject.toml with a semver tag (vX.Y.Z).
# Usage: packaging/sync-version.sh [vX.Y.Z]
# In CI: uses GITHUB_REF_NAME when no arg is passed.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

TAG="${1:-${GITHUB_REF_NAME:-}}"
if [[ -z "${TAG}" ]]; then
  echo "usage: packaging/sync-version.sh vX.Y.Z" >&2
  exit 1
fi

if [[ ! "${TAG}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.-]+)?$ ]]; then
  echo "error: tag must look like vX.Y.Z (got: ${TAG})" >&2
  exit 1
fi

VER="${TAG#v}"
printf '%s\n' "${VER}" > VERSION

python3 - "${VER}" <<'PY'
import pathlib
import re
import sys

ver = sys.argv[1]
path = pathlib.Path("pyproject.toml")
text = path.read_text(encoding="utf-8")
new, n = re.subn(
    r'(?m)^version\s*=\s*"[^"]*"',
    f'version = "{ver}"',
    text,
    count=1,
)
if n != 1:
    raise SystemExit("error: could not patch version in pyproject.toml")
path.write_text(new, encoding="utf-8")
print(f"Synced version {ver}")
PY
