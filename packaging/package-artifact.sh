#!/usr/bin/env bash
# Pack dist/LumiPrintAgent into a stable release archive name.
# Usage: packaging/package-artifact.sh <os> <arch> [outdir]
#   os:   windows | macos | linux
#   arch: x86_64 | arm64 | universal
# Output: LumiPrintAgent-<os>-<arch>-v<ver>.{zip|tar.gz}
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

OS="${1:?os required (windows|macos|linux)}"
ARCH="${2:?arch required}"
OUT_DIR="${3:-${ROOT}/dist}"
DIST="${ROOT}/dist/LumiPrintAgent"

if [[ ! -d "${DIST}" ]]; then
  echo "error: ${DIST} not found; build first" >&2
  exit 1
fi

if [[ ! -f VERSION ]]; then
  echo "error: VERSION missing; run packaging/sync-version.sh first" >&2
  exit 1
fi

VER="$(tr -d '[:space:]' < VERSION)"
NAME="LumiPrintAgent-${OS}-${ARCH}-v${VER}"
mkdir -p "${OUT_DIR}"

# Versión legible junto al exe (updater / bandeja).
cp -f VERSION "${DIST}/VERSION"

case "${OS}" in
  windows)
    ARCHIVE="${OUT_DIR}/${NAME}.zip"
    rm -f "${ARCHIVE}"
    (
      cd "${ROOT}/dist"
      if command -v zip >/dev/null 2>&1; then
        zip -r "${ARCHIVE}" LumiPrintAgent
      else
        python3 - <<PY
import pathlib
import zipfile
root = pathlib.Path("LumiPrintAgent")
out = pathlib.Path(r"${ARCHIVE}")
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
    for path in root.rglob("*"):
        if path.is_file():
            zf.write(path, path.as_posix())
print(out)
PY
      fi
    )
    ;;
  macos|linux)
    ARCHIVE="${OUT_DIR}/${NAME}.tar.gz"
    rm -f "${ARCHIVE}"
    tar -C "${ROOT}/dist" -czf "${ARCHIVE}" LumiPrintAgent
    ;;
  *)
    echo "error: unknown os '${OS}'" >&2
    exit 1
    ;;
esac

# Partial checksum next to the archive (release job merges into SHA256SUMS).
(
  cd "$(dirname "${ARCHIVE}")"
  base="$(basename "${ARCHIVE}")"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${base}" > "${base}.sha256"
  else
    shasum -a 256 "${base}" > "${base}.sha256"
  fi
)

echo "OK: ${ARCHIVE}"
echo "ARTIFACT_PATH=${ARCHIVE}"
echo "ARTIFACT_NAME=$(basename "${ARCHIVE}")"
